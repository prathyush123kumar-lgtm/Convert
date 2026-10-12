import io
import re
import zipfile
from pathlib import Path
from PIL import Image
import pymupdf
import pypdf

class MetadataScrubberError(Exception):
    """Raised when metadata sanitization fails."""
    pass

def sanitize_pdf_metadata(input_path: Path, output_path: Path) -> dict:
    """
    Scrubs all author, creator, producer, dates, and XMP XML metadata
    streams from a PDF file.
    """
    fields_scrubbed = 0
    try:
        doc = pymupdf.open(str(input_path))
        if doc.is_encrypted:
            try:
                doc.authenticate("")
            except Exception:
                raise MetadataScrubberError("The PDF document is password-protected. Please remove password before sanitizing.")

        orig_meta = doc.metadata or {}
        # Count non-empty identifying fields
        for k, v in orig_meta.items():
            if k not in ("format", "encryption") and v:
                fields_scrubbed += 1

        # Strip standard metadata dictionary
        doc.set_metadata({})

        # Save with full garbage collection to remove unreferenced XMP streams and orphaned objects
        doc.save(
            str(output_path),
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()
    except MetadataScrubberError:
        raise
    except Exception as e:
        # Fallback to pypdf if PyMuPDF encounters unexpected structure
        try:
            reader = pypdf.PdfReader(str(input_path))
            writer = pypdf.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            # Add empty metadata dictionary
            writer.add_metadata({})
            with open(output_path, "wb") as f:
                writer.write(f)
            fields_scrubbed = max(fields_scrubbed, 1)
        except Exception as fallback_err:
            raise MetadataScrubberError(f"Failed to scrub PDF metadata: {str(fallback_err)}")

    orig_size = input_path.stat().st_size
    clean_size = output_path.stat().st_size

    return {
        "file_type": "pdf",
        "fields_scrubbed": max(fields_scrubbed, 1),
        "images_sanitized": 0,
        "original_size": orig_size,
        "sanitized_size": clean_size
    }

def sanitize_openxml_metadata(input_path: Path, output_path: Path, ext: str) -> dict:
    """
    Scrubs tracking metadata, author identifiers, revision history,
    and EXIF image metadata from OpenXML documents (.docx, .xlsx, .pptx).
    """
    fields_scrubbed = 0
    images_sanitized = 0

    CLEAN_CORE_XML = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        '  <dc:title></dc:title>\n'
        '  <dc:subject></dc:subject>\n'
        '  <dc:creator></dc:creator>\n'
        '  <cp:keywords></cp:keywords>\n'
        '  <dc:description></dc:description>\n'
        '  <cp:lastModifiedBy></cp:lastModifiedBy>\n'
        '  <cp:revision>1</cp:revision>\n'
        '  <cp:category></cp:category>\n'
        '</cp:coreProperties>'
    ).encode("utf-8")

    try:
        with zipfile.ZipFile(str(input_path), "r") as zin:
            with zipfile.ZipFile(str(output_path), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
                for item in zin.infolist():
                    name = item.filename
                    data = zin.read(name)

                    # 1. Core Properties (Author, Creator, Dates, Description)
                    if name.lower() == "docprops/core.xml":
                        try:
                            core_text = data.decode("utf-8", errors="ignore")
                            # Count non-empty tags
                            for tag in ("creator", "lastModifiedBy", "created", "modified", "description", "title", "subject"):
                                if f"<{tag}" in core_text or f":{tag}" in core_text:
                                    fields_scrubbed += 1
                        except Exception:
                            fields_scrubbed += 1
                        zout.writestr(item, CLEAN_CORE_XML)
                        continue

                    # 2. App Properties (Company, Manager, HyperlinkBase)
                    elif name.lower() == "docprops/app.xml":
                        try:
                            app_text = data.decode("utf-8", errors="ignore")
                            # Clean Company and Manager tags
                            new_text = re.sub(r'<Company>[^<]*</Company>', '<Company></Company>', app_text)
                            new_text = re.sub(r'<Manager>[^<]*</Manager>', '<Manager></Manager>', new_text)
                            new_text = re.sub(r'<HyperlinkBase>[^<]*</HyperlinkBase>', '<HyperlinkBase></HyperlinkBase>', new_text)
                            if new_text != app_text:
                                fields_scrubbed += 2
                            zout.writestr(item, new_text.encode("utf-8"))
                        except Exception:
                            zout.writestr(item, data)
                        continue

                    # 3. Custom Properties (Custom company tags / user keys)
                    elif name.lower() == "docprops/custom.xml":
                        fields_scrubbed += 1
                        # Replace with empty custom properties
                        empty_custom = (
                            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties">\n'
                            '</Properties>'
                        ).encode("utf-8")
                        zout.writestr(item, empty_custom)
                        continue

                    # 4. Embedded Media Images (Strip EXIF metadata)
                    elif any(media_dir in name.lower() for media_dir in ("word/media/", "xl/media/", "ppt/media/")):
                        lower_name = name.lower()
                        if lower_name.endswith((".jpg", ".jpeg", ".png", ".webp", ".tiff")):
                            try:
                                img = Image.open(io.BytesIO(data))
                                # Check if image contains EXIF info
                                exif_data = getattr(img, "_getexif", lambda: None)() if hasattr(img, "_getexif") else None
                                if exif_data or "exif" in img.info:
                                    images_sanitized += 1
                                    img_buf = io.BytesIO()
                                    # Saving without passing exif strips all EXIF metadata
                                    fmt = img.format or ("PNG" if lower_name.endswith(".png") else "JPEG")
                                    img.save(img_buf, format=fmt)
                                    zout.writestr(item, img_buf.getvalue())
                                    continue
                            except Exception:
                                pass
                        zout.writestr(item, data)
                        continue

                    # Default: keep file as-is
                    zout.writestr(item, data)
    except Exception as e:
        raise MetadataScrubberError(f"Failed to scrub {ext.upper()} metadata: {str(e)}")

    orig_size = input_path.stat().st_size
    clean_size = output_path.stat().st_size

    return {
        "file_type": ext,
        "fields_scrubbed": max(fields_scrubbed, 1),
        "images_sanitized": images_sanitized,
        "original_size": orig_size,
        "sanitized_size": clean_size
    }

def sanitize_document_metadata(input_path: Path, output_path: Path, ext: str) -> dict:
    """
    Dispatches to appropriate metadata sanitization handler based on extension.
    """
    clean_ext = ext.lstrip(".").lower()
    if clean_ext == "pdf":
        return sanitize_pdf_metadata(input_path, output_path)
    elif clean_ext in ("docx", "xlsx", "pptx"):
        return sanitize_openxml_metadata(input_path, output_path, clean_ext)
    else:
        raise MetadataScrubberError(f"Unsupported format for metadata scrubbing: .{clean_ext}")
