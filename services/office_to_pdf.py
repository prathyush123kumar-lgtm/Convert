import os
import shutil
import subprocess
from pathlib import Path
from config import find_libreoffice_binary, CONVERSION_TIMEOUT_SECONDS
from services.cleanup import EphemeralWorkspace

class ConversionError(Exception):
    """Raised when document conversion fails."""
    pass

class ConversionTimeoutError(ConversionError):
    """Raised when conversion exceeds allowed time limit."""
    pass

def convert_office_to_pdf(input_file: Path, output_pdf: Path, workspace: EphemeralWorkspace) -> None:
    """
    Converts an Office document (Word, Excel, or PowerPoint) to PDF using
    headless LibreOffice. Preserves fonts, tables, layouts, and embedded charts.
    """
    lo_binary = find_libreoffice_binary()
    if not lo_binary:
        raise ConversionError(
            "LibreOffice is not installed or detected on the server. "
            "Please install LibreOffice to enable Office to PDF conversion."
        )

    # Dedicated isolated profile directory for this conversion to avoid lockfile collisions
    profile_dir = workspace.path / "lo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_uri = profile_dir.as_uri()

    outdir = workspace.path

    ext = input_file.suffix.lstrip(".").lower()
    # Choose specific filter or generic pdf
    export_filter = "pdf"
    if ext in ["docx", "doc"]:
        export_filter = "pdf:writer_pdf_Export"
    elif ext in ["xlsx", "xls"]:
        export_filter = "pdf:calc_pdf_Export"
    elif ext in ["pptx", "ppt"]:
        export_filter = "pdf:impress_pdf_Export"

    cmd = [
        lo_binary,
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to", export_filter,
        "--outdir", str(outdir),
        str(input_file)
    ]

    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=CONVERSION_TIMEOUT_SECONDS,
            startupinfo=startupinfo
        )
    except subprocess.TimeoutExpired:
        raise ConversionTimeoutError(
            f"Office to PDF conversion timed out after {CONVERSION_TIMEOUT_SECONDS} seconds. "
            "The document may contain excessive sheets, slides, or unresolvable assets."
        )
    except Exception:
        raise ConversionError("An error occurred while launching the conversion engine.")

    # LibreOffice writes an output with the same stem as input_file and .pdf extension in outdir
    expected_out = outdir / f"{input_file.stem}.pdf"
    if not expected_out.exists() or expected_out.stat().st_size == 0:
        stderr_msg = result.stderr.strip() if result.stderr else ""
        if "corrupt" in stderr_msg.lower() or "damaged" in stderr_msg.lower():
            raise ConversionError("The document is damaged or corrupted.")
        raise ConversionError("The conversion engine failed to produce a valid PDF output.")

    # Move to target output_pdf if different
    if expected_out.resolve() != output_pdf.resolve():
        if output_pdf.exists():
            output_pdf.unlink()
        shutil.move(str(expected_out), str(output_pdf))

# Alias for backward compatibility
def convert_word_to_pdf(input_docx: Path, output_pdf: Path, workspace: EphemeralWorkspace) -> None:
    convert_office_to_pdf(input_docx, output_pdf, workspace)
