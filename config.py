import os
import shutil
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent

# File Upload & Safety Limits
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))  # 50 MB
CONVERSION_TIMEOUT_SECONDS = int(os.environ.get("CONVERSION_TIMEOUT_SECONDS", 60))

# Allowed extensions mapped to their accepted MIME types & magic signatures
ALLOWED_FORMATS = {
    "docx": {
        "mime": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"],
        "magic": [b"PK\x03\x04"],
        "max_size": 50 * 1024 * 1024
    },
    "doc": {
        "mime": ["application/msword"],
        "magic": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        "max_size": 50 * 1024 * 1024
    },
    "pdf": {
        "mime": ["application/pdf"],
        "magic": [b"%PDF-"],
        "max_size": 50 * 1024 * 1024
    }
}

def find_libreoffice_binary() -> str | None:
    """Detect LibreOffice headless executable across environments."""
    # 1. Custom ENV override
    env_path = os.environ.get("LIBREOFFICE_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. PATH resolution
    which_soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if which_soffice:
        return which_soffice

    # 3. Known Windows locations
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    windows_candidates = [
        str(BASE_DIR / "libreoffice" / "program" / "soffice.exe"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        os.path.join(local_appdata, r"Programs\LibreOffice\program\soffice.exe") if local_appdata else "",
    ]
    for candidate in windows_candidates:
        if candidate and os.path.isfile(candidate):
            return candidate

    # 4. Known Linux / macOS locations
    posix_candidates = [
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/usr/local/bin/soffice",
        "/usr/local/bin/libreoffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for candidate in posix_candidates:
        if os.path.isfile(candidate):
            return candidate

    return None

def find_qpdf_binary() -> str | None:
    """Detect qpdf executable across environments."""
    # 1. Custom ENV override
    env_path = os.environ.get("QPDF_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. PATH resolution
    which_qpdf = shutil.which("qpdf")
    if which_qpdf:
        return which_qpdf

    # 3. Known Windows locations
    windows_candidates = [
        str(BASE_DIR / "qpdf-12.4.2-msvc64" / "bin" / "qpdf.exe"),
        r"C:\Program Files\qpdf\bin\qpdf.exe",
        r"C:\Program Files (x86)\qpdf\bin\qpdf.exe",
    ]
    for candidate in windows_candidates:
        if os.path.isfile(candidate):
            return candidate

    # 4. Known Linux / macOS locations
    posix_candidates = [
        "/usr/bin/qpdf",
        "/usr/local/bin/qpdf",
        "/opt/homebrew/bin/qpdf",
    ]
    for candidate in posix_candidates:
        if os.path.isfile(candidate):
            return candidate

    return None
