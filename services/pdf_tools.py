import re
from pathlib import Path
import pypdf

class PDFToolError(Exception):
    """Base exception for PDF operations."""
    pass

class PDFMergeError(PDFToolError):
    """Raised when PDF merge fails."""
    pass

class PDFSplitError(PDFToolError):
    """Raised when PDF split or page extraction fails."""
    pass

def parse_page_range(range_str: str, total_pages: int) -> list[int]:
    """
    Parses a human-readable page range string like '1-3, 5, 8-10' or 'all'
    into a sorted, deduplicated list of 0-based page indices.
    """
    if not range_str or not range_str.strip():
        raise PDFSplitError("Please specify page numbers or ranges to extract (e.g. 1-3, 5).")

    clean = range_str.strip().lower()
    if clean in ("all", "*"):
        return list(range(total_pages))

    # Split by commas
    tokens = [t.strip() for t in clean.split(",") if t.strip()]
    if not tokens:
        raise PDFSplitError("Invalid page range format.")

    selected_pages: set[int] = set()

    for token in tokens:
        # Check range pattern: X-Y
        range_match = re.fullmatch(r"^(\d+)\s*-\s*(\d+)$", token)
        if range_match:
            start_num = int(range_match.group(1))
            end_num = int(range_match.group(2))

            if start_num < 1 or end_num < 1:
                raise PDFSplitError("Page numbers must be 1 or greater.")
            if start_num > end_num:
                raise PDFSplitError(f"Invalid range '{token}': start page ({start_num}) cannot exceed end page ({end_num}).")
            if end_num > total_pages:
                raise PDFSplitError(
                    f"Page {end_num} is out of range. The document only has {total_pages} page{'s' if total_pages > 1 else ''}."
                )

            for p in range(start_num, end_num + 1):
                selected_pages.add(p - 1)  # 0-indexed
            continue

        # Check single number pattern: X
        single_match = re.fullmatch(r"^(\d+)$", token)
        if single_match:
            page_num = int(single_match.group(1))
            if page_num < 1:
                raise PDFSplitError("Page numbers must be 1 or greater.")
            if page_num > total_pages:
                raise PDFSplitError(
                    f"Page {page_num} is out of range. The document only has {total_pages} page{'s' if total_pages > 1 else ''}."
                )
            selected_pages.add(page_num - 1)  # 0-indexed
            continue

        raise PDFSplitError(f"Unrecognized page specification: '{token}'. Expected formats: '1-3, 5' or '2'.")

    sorted_pages = sorted(selected_pages)
    if not sorted_pages:
        raise PDFSplitError("No valid pages were selected.")

    return sorted_pages

def merge_pdf_documents(input_paths: list[Path], output_path: Path) -> dict:
    """
    Merges multiple PDF files in given sequence into a single PDF document.
    """
    if len(input_paths) < 2:
        raise PDFMergeError("At least 2 PDF files are required to perform a merge.")

    writer = pypdf.PdfWriter()
    total_pages = 0

    for path in input_paths:
        try:
            reader = pypdf.PdfReader(str(path))
            if reader.is_encrypted:
                try:
                    # Attempt empty password decrypt
                    reader.decrypt("")
                except Exception:
                    raise PDFMergeError(f"The document '{path.name}' is password-protected. Please unlock it before merging.")

            for page in reader.pages:
                writer.add_page(page)
                total_pages += 1
        except PDFMergeError:
            raise
        except Exception as e:
            raise PDFMergeError(f"Failed to read PDF '{path.name}': {str(e)}")

    if total_pages == 0:
        raise PDFMergeError("None of the provided PDF documents contained valid pages.")

    try:
        with open(output_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        raise PDFMergeError(f"Failed to write merged PDF document: {str(e)}")

    return {
        "files_merged": len(input_paths),
        "total_pages": total_pages
    }

def split_pdf_document(input_path: Path, output_path: Path, page_range_str: str) -> dict:
    """
    Extracts specified page range from a PDF into a new PDF document.
    """
    try:
        reader = pypdf.PdfReader(str(input_path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise PDFSplitError("The document is password-protected. Please remove password protection before splitting.")
    except PDFSplitError:
        raise
    except Exception as e:
        raise PDFSplitError(f"Failed to read PDF document: {str(e)}")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise PDFSplitError("The uploaded PDF document contains no pages.")

    selected_indices = parse_page_range(page_range_str, total_pages)

    writer = pypdf.PdfWriter()
    for idx in selected_indices:
        writer.add_page(reader.pages[idx])

    try:
        with open(output_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        raise PDFSplitError(f"Failed to save extracted pages: {str(e)}")

    return {
        "original_pages": total_pages,
        "extracted_pages": len(selected_indices),
        "selected_pages_1based": [i + 1 for i in selected_indices]
    }
