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

def convert_word_to_pdf(input_docx: Path, output_pdf: Path, workspace: EphemeralWorkspace) -> None:
    """
    Converts a Word document (.docx or .doc) to PDF using LibreOffice in headless mode.
    Preserves text, tables, images, headings, and layout fidelity.
    """
    lo_binary = find_libreoffice_binary()
    if not lo_binary:
        raise ConversionError(
            "LibreOffice is not installed or detected on the server. "
            "Please install LibreOffice to enable Word to PDF conversion."
        )

    # Dedicated isolated profile for this conversion run to avoid lockfile collisions
    profile_dir = workspace.path / "lo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # Format URI for LibreOffice on Windows and POSIX
    profile_uri = profile_dir.as_uri()

    # Outdir where LibreOffice writes converted file
    outdir = workspace.path

    cmd = [
        lo_binary,
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to", "pdf:writer_pdf_Export",
        "--outdir", str(outdir),
        str(input_docx)
    ]

    try:
        # Prevent popup windows on Windows
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
            f"Word to PDF conversion timed out after {CONVERSION_TIMEOUT_SECONDS} seconds. "
            "The document may contain heavy assets or unresolvable layout macros."
        )
    except Exception as e:
        raise ConversionError("An error occurred while launching the conversion engine.")

    # LibreOffice outputs a file with the same stem as input_docx and .pdf extension in outdir
    expected_out = outdir / f"{input_docx.stem}.pdf"
    if not expected_out.exists() or expected_out.stat().st_size == 0:
        # Check stderr for known issues without exposing stack traces
        stderr_msg = result.stderr.strip() if result.stderr else ""
        if "corrupt" in stderr_msg.lower() or "damaged" in stderr_msg.lower():
            raise ConversionError("The Word document is damaged or corrupted.")
        raise ConversionError("The conversion engine failed to produce a valid PDF output.")

    # Move to target output_pdf if different (use shutil.move for cross-drive safety)
    if expected_out.resolve() != output_pdf.resolve():
        if output_pdf.exists():
            output_pdf.unlink()
        shutil.move(str(expected_out), str(output_pdf))
