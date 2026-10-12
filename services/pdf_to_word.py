import pypdf
from pathlib import Path
from pdf2docx import Converter

class ScannedDocumentError(Exception):
    """Raised when PDF is detected to be scanned or image-only with no text layer."""
    pass

class PasswordProtectedError(Exception):
    """Raised when PDF is encrypted or password-protected."""
    pass

class PDFToWordError(Exception):
    """Raised when PDF to Word conversion fails."""
    pass

def inspect_pdf_text_suitability(input_pdf: Path) -> dict:
    """
    Inspects PDF pages to detect encrypted, empty, or scanned documents.
    Returns metadata including page count, total character count, and image presence.
    """
    try:
        reader = pypdf.PdfReader(str(input_pdf))
    except Exception as e:
        raise PDFToWordError("Unable to read PDF file structure. The file may be corrupt.")

    if reader.is_encrypted:
        raise PasswordProtectedError("The PDF document is password-protected. Please remove the password before converting.")

    num_pages = len(reader.pages)
    if num_pages == 0:
        raise PDFToWordError("The PDF document contains no pages.")

    total_chars = 0
    pages_with_images = 0
    pages_with_text = 0

    for page in reader.pages:
        try:
            text = (page.extract_text() or "").strip()
            char_count = len(text)
            total_chars += char_count
            if char_count > 10:
                pages_with_text += 1
            if len(page.images) > 0:
                pages_with_images += 1
        except Exception:
            pass

    # Evaluation: If no text exists or document is solely raster images with negligible text
    avg_chars_per_page = total_chars / num_pages if num_pages > 0 else 0

    is_scanned = False
    if total_chars == 0:
        is_scanned = True
    elif num_pages <= 3 and total_chars < 20:
        is_scanned = True
    elif avg_chars_per_page < 15 and pages_with_images >= (num_pages * 0.75):
        is_scanned = True

    if is_scanned:
        raise ScannedDocumentError(
            "This document appears to be a scanned or image-only PDF with no selectable text layer. "
            "pdf2docx requires text-based PDFs to reconstruct layouts and tables. "
            "Please apply Optical Character Recognition (OCR) to make the text searchable before converting."
        )

    return {
        "num_pages": num_pages,
        "total_chars": total_chars,
        "pages_with_text": pages_with_text
    }

def convert_pdf_to_word(input_pdf: Path, output_docx: Path) -> dict:
    """
    Converts a text-based PDF to DOCX using pdf2docx.
    First performs scanned-document and encryption detection.
    """
    # 1. Pre-flight check
    meta = inspect_pdf_text_suitability(input_pdf)

    # 2. Convert using pdf2docx
    cv = None
    try:
        cv = Converter(str(input_pdf))
        # Convert all pages
        cv.convert(str(output_docx), start=0, end=None)
    except (ScannedDocumentError, PasswordProtectedError):
        raise
    except Exception as e:
        raise PDFToWordError(
            "Failed to convert PDF to Word. The document structure or embedded fonts may be incompatible."
        )
    finally:
        if cv:
            try:
                cv.close()
            except Exception:
                pass

    if not output_docx.exists() or output_docx.stat().st_size == 0:
        raise PDFToWordError("Conversion completed but no output Word file was generated.")

    return meta
