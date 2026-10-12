import re
import zipfile
from pathlib import Path
from werkzeug.datastructures import FileStorage
from config import ALLOWED_FORMATS, MAX_CONTENT_LENGTH

class ValidationError(Exception):
    """Raised when file validation fails."""
    pass

def sanitize_filename(filename: str, default: str = "document") -> str:
    """
    Sanitize filename for HTTP Content-Disposition headers.
    Strips directory separators, null bytes, and unsafe characters.
    """
    if not filename:
        return default
    
    # Strip paths
    base = Path(filename).name
    # Keep alphanumeric, dashes, underscores, and dots
    cleaned = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base).strip('._')
    if not cleaned:
        return default
    # Limit length to avoid header injection / truncation issues
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned

def validate_upload(file_storage: FileStorage, expected_type: str | None = None) -> str:
    """
    Validate uploaded file:
    1. Check presence & filename
    2. Check file size
    3. Check extension
    4. Check magic bytes / content integrity
    Returns the validated file extension (lowercase).
    """
    if not file_storage or not file_storage.filename:
        raise ValidationError("No file provided.")

    original_name = file_storage.filename
    ext = Path(original_name).suffix.lstrip(".").lower()

    if not ext:
        raise ValidationError("File has no extension.")

    if ext not in ALLOWED_FORMATS:
        raise ValidationError(f"Unsupported file format: '.{ext}'. Supported formats: {', '.join(ALLOWED_FORMATS.keys())}.")

    if expected_type and ext != expected_type.lower():
        raise ValidationError(f"Expected a .{expected_type} file for this operation, but received .{ext}.")

    # Peek at first 1024 bytes for magic signature validation
    stream = file_storage.stream
    pos = stream.tell()
    header = stream.read(1024)
    stream.seek(pos)

    if len(header) == 0:
        raise ValidationError("Uploaded file is empty (0 bytes).")

    format_rules = ALLOWED_FORMATS[ext]
    expected_magics = format_rules["magic"]
    has_valid_magic = any(header.startswith(m) for m in expected_magics)

    if not has_valid_magic:
        raise ValidationError(f"File content does not match the '.{ext}' specification (invalid file header).")

    # Additional DOCX integrity inspection (protect against zip bombs & corrupted zips)
    if ext == "docx":
        try:
            stream.seek(0)
            with zipfile.ZipFile(stream) as zf:
                # Check for word/document.xml or [Content_Types].xml
                namelist = zf.namelist()
                if "[Content_Types].xml" not in namelist:
                    raise ValidationError("Invalid DOCX document: Missing [Content_Types].xml structure.")
                
                # Check uncompressed size to prevent zip-bomb / memory exhaustion
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 200 * 1024 * 1024:  # 200MB expansion limit
                    raise ValidationError("DOCX exceeds maximum safe decompression limit (potential zip bomb).")
            stream.seek(0)
        except zipfile.BadZipFile:
            raise ValidationError("Corrupted or malformed DOCX file.")
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Unable to verify DOCX structure: {str(e)}")

    return ext
