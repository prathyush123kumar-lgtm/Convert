import os
import shutil
import subprocess
from pathlib import Path
import pypdf
from config import find_qpdf_binary, CONVERSION_TIMEOUT_SECONDS
from services.cleanup import EphemeralWorkspace

class PDFCompressionError(Exception):
    """Raised when PDF compression fails."""
    pass

def compress_pdf_lossless(input_pdf: Path, output_pdf: Path, workspace: EphemeralWorkspace) -> dict:
    """
    Performs lossless PDF compression using qpdf (with pypdf fallback).
    Never downsamples images or degrades visual fidelity.
    Reports original size, compressed size, and percentage saved only when genuine reduction occurs.
    """
    orig_size = input_pdf.stat().st_size
    if orig_size == 0:
        raise PDFCompressionError("Input PDF is empty (0 bytes).")

    qpdf_bin = find_qpdf_binary()
    success = False

    # 1. Attempt qpdf lossless compression
    if qpdf_bin:
        temp_out = workspace.secure_path(suffix=".pdf")
        cmd = [
            qpdf_bin,
            "--compress-streams=y",
            "--recompress-flate",
            "--object-streams=generate",
            str(input_pdf),
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
            # Exit code 0 is success; exit code 3 is warnings but successful output
            if res.returncode in (0, 3) and temp_out.exists() and temp_out.stat().st_size > 0:
                if output_pdf.exists():
                    output_pdf.unlink()
                shutil.move(str(temp_out), str(output_pdf))
                success = True
        except subprocess.TimeoutExpired:
            raise PDFCompressionError("PDF compression timed out.")
        except Exception:
            success = False

    # 2. Fallback to pypdf lossless stream recompression if qpdf was unavailable or failed
    if not success:
        try:
            reader = pypdf.PdfReader(str(input_pdf))
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
        except Exception as e:
            raise PDFCompressionError("Failed to compress PDF.")

    if not output_pdf.exists() or output_pdf.stat().st_size == 0:
        raise PDFCompressionError("Failed to produce compressed PDF output.")

    comp_size = output_pdf.stat().st_size

    # 3. Check if actual reduction occurred
    if comp_size < orig_size:
        saved_bytes = orig_size - comp_size
        pct = round((saved_bytes / orig_size) * 100, 1)
        is_reduced = True
        msg = f"Document compressed losslessly: saved {pct}% ({saved_bytes:,} bytes)."
    else:
        # Prevent bloating: deliver original file if lossless compression did not reduce size
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
        "message": msg
    }
