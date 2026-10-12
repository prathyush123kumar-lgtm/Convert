import sys
import io
import os
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image, ImageDraw, ImageFont
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import pypdf

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

def generate_fixtures():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating rich test fixtures in: {FIXTURES_DIR}")

    # 1. Complex Word Document (Tables, Images, Headings, Columns, Header/Footer)
    complex_docx_path = FIXTURES_DIR / "complex_document.docx"
    doc = docx.Document()

    # Set Header & Footer
    section = doc.sections[0]
    header = section.header
    header.paragraphs[0].text = "CONFIDENTIAL · PrivDoc Test Benchmark · Header"
    footer = section.footer
    footer.paragraphs[0].text = "Page 1 of 1 · Zero Data Retention Protocol"

    # Title & Heading
    title = doc.add_heading("Financial & Technical Summary Report", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_intro = doc.add_paragraph()
    run1 = p_intro.add_run("This document evaluates layout preservation, typography, tables, and images. ")
    run1.font.size = Pt(11)
    run2 = p_intro.add_run("All data is simulated and processed ephemerally.")
    run2.bold = True
    run2.font.color.rgb = RGBColor(16, 185, 129)

    doc.add_heading("1. Multi-Dimensional Performance Metrics", level=1)
    
    # Complex Table
    table = doc.add_table(rows=4, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    headers = ["Metric ID", "System Component", "Throughput (ops/s)", "Latency (p99)"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        for p in cell.paragraphs:
            p.runs[0].bold = True

    data = [
        ["M-101", "Word to PDF Engine", "45 docs/min", "1.2s"],
        ["M-102", "PDF to Word Engine", "38 docs/min", "1.6s"],
        ["M-103", "Lossless Stream Shrinker", "120 docs/min", "0.3s"],
    ]
    for r_idx, row in enumerate(data, start=1):
        for c_idx, val in enumerate(row):
            table.cell(r_idx, c_idx).text = val

    doc.add_heading("2. Embedded Media & Image Representation", level=1)
    
    # Generate a sample diagram image with Pillow
    img = Image.new("RGB", (600, 300), color=(240, 244, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 580, 280], outline=(16, 185, 129), width=3)
    draw.text((50, 60), "PrivDoc Secure Pipeline Architecture", fill=(17, 24, 39))
    draw.rectangle([50, 110, 200, 190], fill=(59, 130, 246))
    draw.text((65, 140), "Ephemeral RAM", fill=(255, 255, 255))
    draw.rectangle([240, 110, 390, 190], fill=(16, 185, 129))
    draw.text((260, 140), "Conversion", fill=(255, 255, 255))
    draw.rectangle([430, 110, 560, 190], fill=(239, 68, 68))
    draw.text((455, 140), "Auto-Purge", fill=(255, 255, 255))
    draw.line([200, 150, 240, 150], fill=(100, 116, 139), width=3)
    draw.line([390, 150, 430, 150], fill=(100, 116, 139), width=3)

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    doc.add_picture(img_buf, width=Inches(5.0))
    p_caption = doc.add_paragraph("Figure 1: High-fidelity zero-retention conversion pipeline.")
    p_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading("3. Extensive Text & Columnar Paragraphs", level=1)
    p_long = doc.add_paragraph(
        "Privacy-preserving document processing requires careful lifecycle management. "
        "Every operation executes in a dedicated sandbox created with cryptographic entropy. "
        "Upon response dispatch or unhandled fault, the complete directory hierarchy is unlinked "
        "and securely wiped from filesystem tables. No metadata or contents ever leak into logs."
    )

    doc.save(str(complex_docx_path))
    print(f"Created: {complex_docx_path}")

    # 2. Text-based PDF (convert from complex_document.docx using LibreOffice)
    from config import find_libreoffice_binary
    from services.cleanup import EphemeralWorkspace
    from services.office_to_pdf import convert_word_to_pdf

    text_pdf_path = FIXTURES_DIR / "text_document.pdf"
    with EphemeralWorkspace(prefix="gen_fixture_") as ws:
        convert_word_to_pdf(complex_docx_path, text_pdf_path, ws)
    print(f"Created: {text_pdf_path}")

    # 3. Pure Scanned / Image-Only PDF (Zero selectable text, simulated scanner output)
    scanned_pdf_path = FIXTURES_DIR / "scanned_image_only.pdf"
    scan_img = Image.new("RGB", (800, 1100), color=(255, 255, 255))
    s_draw = ImageDraw.Draw(scan_img)
    # Draw simulated scanned text pixels without OCR layer
    s_draw.rectangle([50, 50, 750, 1050], outline=(220, 220, 220), width=1)
    s_draw.text((80, 100), "SCANNED MEDICAL DOCUMENT (IMAGE ONLY)", fill=(20, 20, 20))
    s_draw.text((80, 140), "Patient Name: Simulated Patient", fill=(40, 40, 40))
    s_draw.text((80, 170), "Diagnosis: Paper Scan Simulator", fill=(40, 40, 40))
    s_draw.text((80, 200), "Note: This file contains NO text stream. It is pure raster pixels.", fill=(80, 80, 80))
    
    # Save directly as image PDF
    scan_img.save(str(scanned_pdf_path), "PDF", resolution=150.0)
    print(f"Created: {scanned_pdf_path}")

    # 4. Large Image Word Document (For testing image optimization)
    huge_img_docx = FIXTURES_DIR / "huge_image_document.docx"
    doc_huge = docx.Document()
    doc_huge.add_heading("Photo Heavy Document", 0)
    doc_huge.add_paragraph("This document contains a large uncompressed test image to test image optimization.")

    large_img = Image.new("RGB", (2500, 2500), color=(100, 150, 200))
    l_draw = ImageDraw.Draw(large_img)
    for x in range(0, 2500, 100):
        l_draw.line([(x, 0), (x, 2500)], fill=(120, 170, 220), width=2)
    large_img_buf = io.BytesIO()
    # Save as high quality PNG
    large_img.save(large_img_buf, format="PNG")
    large_img_buf.seek(0)
    doc_huge.add_picture(large_img_buf, width=Inches(5.5))
    doc_huge.save(str(huge_img_docx))
    print(f"Created: {huge_img_docx}")

    # 5. Malformed DOCX (invalid zip)
    malformed_docx = FIXTURES_DIR / "malformed.docx"
    with open(malformed_docx, "wb") as f:
        f.write(b"PK\x03\x04\x00\x00CORRUPTED_ZIP_BYTES_NOT_A_VALID_DOCUMENT_STRUCTURE")
    print(f"Created: {malformed_docx}")

    # 6. Malformed PDF (invalid header/truncated)
    malformed_pdf = FIXTURES_DIR / "malformed.pdf"
    with open(malformed_pdf, "wb") as f:
        f.write(b"%PDF-1.4\n%TRUNCATED_AND_BROKEN_PDF_FILE")
    print(f"Created: {malformed_pdf}")

    # 7. Sample Spreadsheet (.xlsx)
    xlsx_path = FIXTURES_DIR / "spreadsheet.xlsx"
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financial Summary"
    ws.append(["Department", "Q1 Budget", "Q2 Budget", "Q3 Budget", "Q4 Budget"])
    ws.append(["Engineering", 150000, 160000, 155000, 170000])
    ws.append(["Security & Compliance", 95000, 98000, 102000, 110000])
    ws.append(["Design & UX", 45000, 48000, 52000, 55000])
    wb.save(str(xlsx_path))
    print(f"Created: {xlsx_path}")

    # 8. Sample Presentation (.pptx)
    pptx_path = FIXTURES_DIR / "presentation.pptx"
    import pptx
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "PrivDoc Zero Retention Architecture"
    slide.placeholders[1].text = "Security, Privacy, and High Throughput"
    prs.save(str(pptx_path))
    print(f"Created: {pptx_path}")

    # 9. Multi-page PDF for Merge & Split tests
    multipage_pdf_path = FIXTURES_DIR / "multi_page_sample.pdf"
    writer = pypdf.PdfWriter()
    for page_num in range(1, 5):
        p_img = Image.new("RGB", (600, 800), color=(255, 255, 255))
        d = ImageDraw.Draw(p_img)
        d.text((100, 150), f"PrivDoc Document Page {page_num}", fill=(20, 20, 20))
        d.text((100, 200), f"This is page {page_num} of 4 in the benchmark test document.", fill=(60, 60, 60))
        d.rectangle([50, 50, 550, 750], outline=(100, 100, 100), width=2)
        p_buf = io.BytesIO()
        p_img.save(p_buf, "PDF")
        p_buf.seek(0)
        p_reader = pypdf.PdfReader(p_buf)
        writer.add_page(p_reader.pages[0])
    with open(multipage_pdf_path, "wb") as f:
        writer.write(f)
    print(f"Created: {multipage_pdf_path}")

    # 10. Document with Tracking Metadata for Scrubber test
    meta_docx_path = FIXTURES_DIR / "doc_with_metadata.docx"
    doc_meta = docx.Document()
    core_props = doc_meta.core_properties
    core_props.author = "John Doe Secret Author"
    core_props.comments = "Confidential internal metadata notes"
    core_props.title = "Internal Security Audit"
    core_props.subject = "Confidential Investigation"
    doc_meta.add_heading("Internal Security Audit", 0)
    doc_meta.add_paragraph("This document has identifying metadata tags.")
    doc_meta.save(str(meta_docx_path))
    print(f"Created: {meta_docx_path}")

    print("All fixtures generated successfully.")

if __name__ == "__main__":
    generate_fixtures()

