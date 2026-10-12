import io
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image
import pymupdf
import pypdf
from config import find_qpdf_binary, CONVERSION_TIMEOUT_SECONDS
from services.cleanup import EphemeralWorkspace

class PDFCompressionError(Exception):
    """Raised when PDF compression fails."""
    pass

def compress_pdf(
    input_pdf: Path,
    output_pdf: Path,
    workspace: EphemeralWorkspace,
    strong_mode: bool = False
) -> dict:
    """
    Performs PDF compression:
    - Default (strong_mode=False): 100% lossless structural and stream optimization via QPDF / pypdf.
      Never touches or downsamples embedded images.
    - Optional (strong_mode=True): Stronger compression mode that optimizes embedded image streams.
    """
    orig_size = input_pdf.stat().st_size
    if orig_size == 0:
        raise PDFCompressionError("Input PDF is empty (0 bytes).")

    working_input = input_pdf

    # 1. If strong_mode is requested, optimize embedded images first
    images_optimized_count = 0
    if strong_mode:
        try:
            doc = pymupdf.open(str(input_pdf))
            if not doc.is_encrypted:
                modified = False
                for page in doc:
                    for img_info in page.get_images():
                        xref = img_info[0]
                        try:
                            base_img = doc.extract_image(xref)
                            raw_bytes = base_img["image"]
                            
                            with Image.open(io.BytesIO(raw_bytes)) as img:
                                max_dim = 1920
                                w, h = img.size
                                if w > max_dim or h > max_dim:
                                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                                
                                out_buf = io.BytesIO()
                                if img.mode in ("RGBA", "P"):
                                    img = img.convert("RGB")
                                img.save(out_buf, format="JPEG", quality=78, optimize=True)
                                
                                opt_bytes = out_buf.getvalue()
                                if len(opt_bytes) < len(raw_bytes):
                                    doc.update_stream(xref, opt_bytes)
                                    images_optimized_count += 1
                                    modified = True
                        except Exception:
                            continue
                
                if modified:
                    strong_intermediate = workspace.secure_path(suffix="_strong.pdf")
                    doc.save(str(strong_intermediate), garbage=4, deflate=True)
                    working_input = strong_intermediate
            doc.close()
        except Exception:
            # Fall back safely to standard lossless if image optimization fails
            working_input = input_pdf

    # 2. QPDF lossless structural compression
    qpdf_bin = find_qpdf_binary()
    success = False

    if qpdf_bin:
        temp_out = workspace.secure_path(suffix=".pdf")
        cmd = [
            qpdf_bin,
            "--compress-streams=y",
            "--recompress-flate",
            "--object-streams=generate",
            str(working_input),
            str(temp_out)
        ]
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=CONVERSION_TIMEOUT_SECONDS,
                startupinfo=startupinfo
            )
            if res.returncode in (0, 3) and temp_out.exists() and temp_out.stat().st_size > 0:
                if output_pdf.exists():
                    output_pdf.unlink()
                shutil.move(str(temp_out), str(output_pdf))
                success = True
        except subprocess.TimeoutExpired:
            raise PDFCompressionError("PDF compression timed out.")
        except Exception:
            success = False

    # 3. Fallback to pypdf lossless stream recompression if QPDF is unavailable or failed
    if not success:
        try:
            reader = pypdf.PdfReader(str(working_input))
            if reader.is_encrypted:
                raise PDFCompressionError("Password-protected PDFs cannot be compressed without the decryption key.")
            writer = pypdf.PdfWriter(clone_from=reader)
            for page in writer.pages:
                page.compress_content_streams()
            with open(output_pdf, "wb") as f:
                writer.write(f)
            success = True
        except PDFCompressionError:
            raise
        except Exception:
            raise PDFCompressionError("Failed to compress PDF.")

    if not output_pdf.exists() or output_pdf.stat().st_size == 0:
        raise PDFCompressionError("Failed to produce compressed PDF output.")

    comp_size = output_pdf.stat().st_size

    # 4. Check if actual reduction occurred
    if comp_size < orig_size:
        saved_bytes = orig_size - comp_size
        pct = round((saved_bytes / orig_size) * 100, 1)
        is_reduced = True
        mode_label = "Strong mode" if strong_mode else "Lossless"
        msg = f"{mode_label} compression: saved {pct}% ({saved_bytes:,} bytes)."
        if strong_mode and images_optimized_count > 0:
            msg += f" (Optimized {images_optimized_count} embedded images)."
    else:
        # Prevent bloating: deliver original file if compression did not reduce size
        shutil.copy2(input_pdf, output_pdf)
        comp_size = orig_size
        saved_bytes = 0
        pct = 0.0
        is_reduced = False
        msg = "Document is already optimally compressed losslessly. No quality degradation was applied."

    return {
        "original_size": orig_size,
        "compressed_size": comp_size,
        "saved_bytes": saved_bytes,
        "percent_saved": pct,
        "is_reduced": is_reduced,
        "message": msg,
        "strong_mode": strong_mode,
        "images_optimized": images_optimized_count
    }

# Backward compatibility alias
compress_pdf_lossless = compress_pdf
