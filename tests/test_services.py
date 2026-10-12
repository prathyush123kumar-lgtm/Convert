import sys
import unittest
from pathlib import Path
import pypdf
import docx

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.cleanup import EphemeralWorkspace
from services.validator import validate_upload, sanitize_filename, ValidationError
from services.word_to_pdf import convert_word_to_pdf, ConversionError
from services.pdf_to_word import convert_pdf_to_word, ScannedDocumentError, inspect_pdf_text_suitability
from services.compress_pdf import compress_pdf_lossless
from services.compress_word import compress_word_document
from werkzeug.datastructures import FileStorage
import io

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

class TestDocumentServices(unittest.TestCase):

    def test_ephemeral_workspace_guaranteed_cleanup(self):
        """Verify temporary directories and files are guaranteed purged on exit and exception."""
        ws_path = None
        with EphemeralWorkspace(prefix="test_clean_") as ws:
            ws_path = ws.path
            self.assertTrue(ws_path.exists())
            test_file = ws.secure_path(suffix=".txt")
            test_file.write_text("sensitivedata")
            self.assertTrue(test_file.exists())

        # Outside context: workspace must not exist
        self.assertFalse(ws_path.exists())

        # Test cleanup on exception
        exc_ws_path = None
        try:
            with EphemeralWorkspace(prefix="test_exc_") as ws:
                exc_ws_path = ws.path
                self.assertTrue(exc_ws_path.exists())
                f = ws.secure_path(suffix=".dat")
                f.write_text("data")
                raise RuntimeError("Simulated crash")
        except RuntimeError:
            pass

        self.assertFalse(exc_ws_path.exists())

    def test_sanitize_filename(self):
        """Verify filenames are properly sanitized to prevent directory traversal and header injection."""
        self.assertEqual(sanitize_filename("../../secret.docx"), "secret.docx")
        self.assertEqual(sanitize_filename("valid_doc.docx"), "valid_doc.docx")
        self.assertEqual(sanitize_filename(""), "document")
        self.assertEqual(sanitize_filename("my report (2026) #1.pdf"), "my_report__2026___1.pdf")

    def test_word_to_pdf_conversion(self):
        """Test Word to PDF conversion preserves document structure."""
        complex_docx = FIXTURES_DIR / "complex_document.docx"
        self.assertTrue(complex_docx.exists())

        with EphemeralWorkspace(prefix="test_w2p_") as ws:
            output_pdf = ws.secure_path(suffix=".pdf")
            convert_word_to_pdf(complex_docx, output_pdf, ws)

            self.assertTrue(output_pdf.exists())
            self.assertGreater(output_pdf.stat().st_size, 1000)

            # Inspect converted PDF
            reader = pypdf.PdfReader(str(output_pdf))
            self.assertGreaterEqual(len(reader.pages), 1)
            # Ensure text is selectable in generated PDF
            extracted_text = "".join(page.extract_text() for page in reader.pages)
            self.assertIn("Financial & Technical Summary Report", extracted_text)
            self.assertIn("Multi-Dimensional Performance Metrics", extracted_text)

    def test_pdf_to_word_conversion_text_based(self):
        """Test PDF to Word conversion using pdf2docx for text-based PDFs."""
        text_pdf = FIXTURES_DIR / "text_document.pdf"
        self.assertTrue(text_pdf.exists())

        with EphemeralWorkspace(prefix="test_p2w_") as ws:
            output_docx = ws.secure_path(suffix=".docx")
            meta = convert_pdf_to_word(text_pdf, output_docx, ws)

            self.assertTrue(output_docx.exists())
            self.assertGreater(output_docx.stat().st_size, 1000)
            self.assertGreater(meta["total_chars"], 50)

            # Inspect resulting docx
            doc = docx.Document(str(output_docx))
            full_text = " ".join([p.text for p in doc.paragraphs])
            self.assertTrue("Financial" in full_text or len(doc.tables) > 0)

    def test_pdf_to_word_scanned_detection(self):
        """Verify scanned / image-only PDFs are detected and raise ScannedDocumentError."""
        scanned_pdf = FIXTURES_DIR / "scanned_image_only.pdf"
        self.assertTrue(scanned_pdf.exists())

        with EphemeralWorkspace(prefix="test_scan_") as ws:
            output_docx = ws.secure_path(suffix=".docx")
            with self.assertRaises(ScannedDocumentError) as ctx:
                convert_pdf_to_word(scanned_pdf, output_docx, ws)
            self.assertIn("scanned or image-only", str(ctx.exception).lower())
            self.assertIn("ocr", str(ctx.exception).lower())

    def test_compress_pdf_lossless(self):
        """Test lossless PDF compression reports genuine reductions or optimal state."""
        text_pdf = FIXTURES_DIR / "text_document.pdf"
        self.assertTrue(text_pdf.exists())

        with EphemeralWorkspace(prefix="test_cmp_pdf_") as ws:
            output_pdf = ws.secure_path(suffix=".pdf")
            stats = compress_pdf_lossless(text_pdf, output_pdf, ws)

            self.assertTrue(output_pdf.exists())
            self.assertIn("original_size", stats)
            self.assertIn("compressed_size", stats)
            self.assertIn("percent_saved", stats)
            self.assertIn("is_reduced", stats)
            # Size must never be larger than original
            self.assertLessEqual(stats["compressed_size"], stats["original_size"])

    def test_compress_pdf_strong_mode(self):
        """Test strong mode PDF compression optimizing embedded images."""
        text_pdf = FIXTURES_DIR / "text_document.pdf"
        self.assertTrue(text_pdf.exists())

        with EphemeralWorkspace(prefix="test_cmp_pdf_strong_") as ws:
            output_pdf = ws.secure_path(suffix=".pdf")
            stats = compress_pdf_lossless(text_pdf, output_pdf, ws, strong_mode=True)

            self.assertTrue(output_pdf.exists())
            self.assertTrue(stats["strong_mode"])
            self.assertLessEqual(stats["compressed_size"], stats["original_size"])

    def test_compress_word_safe_and_image_optimization(self):
        """Test safe Word compression and optional embedded image optimization."""
        huge_doc = FIXTURES_DIR / "huge_image_document.docx"
        self.assertTrue(huge_doc.exists())

        # 1. Safe mode (no image downsampling)
        with EphemeralWorkspace(prefix="test_w_safe_") as ws:
            output_safe = ws.secure_path(suffix=".docx")
            stats_safe = compress_word_document(huge_doc, output_safe, ws, optimize_images=False)
            self.assertTrue(output_safe.exists())
            self.assertEqual(stats_safe["images_optimized"], 0)

        # 2. Image optimization mode
        with EphemeralWorkspace(prefix="test_w_img_") as ws:
            output_opt = ws.secure_path(suffix=".docx")
            stats_opt = compress_word_document(huge_doc, output_opt, ws, optimize_images=True)
            self.assertTrue(output_opt.exists())
            self.assertTrue(stats_opt["is_reduced"])
            self.assertGreater(stats_opt["percent_saved"], 0.0)
            self.assertGreater(stats_opt["images_optimized"], 0)

if __name__ == "__main__":
    unittest.main()
