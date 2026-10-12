import io
import shutil
import zipfile
from pathlib import Path
from PIL import Image
from services.cleanup import EphemeralWorkspace

class WordCompressionError(Exception):
    """Raised when Word document compression fails."""
    pass

def compress_word_document(
    input_docx: Path,
    output_docx: Path,
    workspace: EphemeralWorkspace,
    optimize_images: bool = False
) -> dict:
    """
    Compresses a Word document (.docx).
    - By default, performs safe lossless archive and XML re-compression (compresslevel=9).
    - If optimize_images is True, selectively recompresses oversized embedded media (with warning).
    """
    orig_size = input_docx.stat().st_size
    if orig_size == 0:
        raise WordCompressionError("Input Word document is empty (0 bytes).")

    try:
        temp_out = workspace.secure_path(suffix=".docx")
        images_optimized_count = 0

        with zipfile.ZipFile(input_docx, "r") as zin:
            with zipfile.ZipFile(temp_out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    
                    # Optional embedded media optimization
                    if optimize_images and item.filename.startswith("word/media/"):
                        ext = item.filename.split(".")[-1].lower()
                        if ext in ("jpg", "jpeg", "png", "bmp", "tiff"):
                            try:
                                with Image.open(io.BytesIO(data)) as img:
                                    # Convert RGBA to RGB for JPEG if applicable
                                    img_format = "JPEG" if ext in ("jpg", "jpeg") else "PNG"
                                    
                                    # Resize oversized photos
                                    max_dim = 1920
                                    w, h = img.size
                                    if w > max_dim or h > max_dim:
                                        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                                    out_buf = io.BytesIO()
                                    if img_format == "JPEG":
                                        if img.mode in ("RGBA", "P"):
                                            img = img.convert("RGB")
                                        img.save(out_buf, format="JPEG", quality=82, optimize=True)
                                    else:
                                        img.save(out_buf, format="PNG", optimize=True)
                                    
                                    optimized_data = out_buf.getvalue()
                                    # Only adopt if genuinely smaller
                                    if len(optimized_data) < len(data):
                                        data = optimized_data
                                        images_optimized_count += 1
                            except Exception:
                                # Preserve original media on any processing hiccup
                                pass

                    zout.writestr(item, data)

        comp_size = temp_out.stat().st_size

        if comp_size < orig_size:
            if output_docx.exists():
                output_docx.unlink()
            shutil.move(str(temp_out), str(output_docx))
            saved_bytes = orig_size - comp_size
            pct = round((saved_bytes / orig_size) * 100, 1)
            is_reduced = True
            msg = f"Word document compressed: saved {pct}% ({saved_bytes:,} bytes)."
            if optimize_images and images_optimized_count > 0:
                msg += f" (Optimized {images_optimized_count} embedded images)."
        else:
            # Revert to original if no reduction achieved
            shutil.copy2(input_docx, output_docx)
            comp_size = orig_size
            saved_bytes = 0
            pct = 0.0
            is_reduced = False
            msg = "Document is already optimally compressed. No size reduction was possible without losing data."

        return {
            "original_size": orig_size,
            "compressed_size": comp_size,
            "saved_bytes": saved_bytes,
            "percent_saved": pct,
            "is_reduced": is_reduced,
            "message": msg,
            "images_optimized": images_optimized_count
        }

    except zipfile.BadZipFile:
        raise WordCompressionError("Invalid or corrupted DOCX archive.")
    except Exception as e:
        raise WordCompressionError(f"Word compression failed: {str(e)}")
