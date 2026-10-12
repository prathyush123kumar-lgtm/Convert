import sys
import unittest
from pathlib import Path
import io

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

class TestAPIRoutes(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_index_route_and_security_headers(self):
        """Verify index route renders correctly with strict privacy and security headers."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"PrivDoc", res.data)
        self.assertIn("Cache-Control", res.headers)
        self.assertIn("no-store", res.headers["Cache-Control"])
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")

    def test_system_status_endpoint(self):
        """Verify /api/system-status reports operational state."""
        res = self.client.get("/api/system-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ready")
        self.assertIn("libreoffice_available", data)
        self.assertIn("qpdf_available", data)

    def test_word_to_pdf_route_success(self):
        """End-to-end Word to PDF upload, conversion, and download."""
        docx_path = FIXTURES_DIR / "complex_document.docx"
        with open(docx_path, "rb") as f:
            data = {
                "file": (f, "complex_document.docx")
            }
            res = self.client.post(
                "/api/convert/word-to-pdf",
                data=data,
                content_type="multipart/form-data"
            )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "application/pdf")
        self.assertIn("attachment", res.headers.get("Content-Disposition", ""))
        self.assertTrue(res.data.startswith(b"%PDF-"))

    def test_pdf_to_word_route_success(self):
        """End-to-end PDF to Word upload, conversion, and download."""
        pdf_path = FIXTURES_DIR / "text_document.pdf"
        with open(pdf_path, "rb") as f:
            data = {
                "file": (f, "text_document.pdf")
            }
            res = self.client.post(
                "/api/convert/pdf-to-word",
                data=data,
                content_type="multipart/form-data"
            )

        self.assertEqual(res.status_code, 200)
        self.assertIn("wordprocessingml", res.headers.get("Content-Type", ""))
        self.assertIn("attachment", res.headers.get("Content-Disposition", ""))
        self.assertTrue(res.data.startswith(b"PK\x03\x04"))

    def test_pdf_to_word_scanned_rejection(self):
        """Verify scanned PDFs return 422 with clear OCR advisory."""
        scanned_path = FIXTURES_DIR / "scanned_image_only.pdf"
        with open(scanned_path, "rb") as f:
            data = {
                "file": (f, "scanned_image_only.pdf")
            }
            res = self.client.post(
                "/api/convert/pdf-to-word",
                data=data,
                content_type="multipart/form-data"
            )

        self.assertEqual(res.status_code, 422)
        json_data = res.get_json()
        self.assertEqual(json_data.get("code"), "SCANNED_DOCUMENT")
        self.assertTrue(json_data.get("ocr_required"))
        self.assertIn("ocr", json_data.get("error", "").lower())

    def test_compress_pdf_route(self):
        """Verify PDF compression route returns valid file and metrics headers."""
        pdf_path = FIXTURES_DIR / "text_document.pdf"
        with open(pdf_path, "rb") as f:
            data = {
                "file": (f, "text_document.pdf")
            }
            res = self.client.post(
                "/api/compress/pdf",
                data=data,
                content_type="multipart/form-data"
            )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "application/pdf")
        self.assertIn("X-Original-Size", res.headers)
        self.assertIn("X-Compressed-Size", res.headers)
        self.assertIn("X-Percent-Saved", res.headers)
        self.assertTrue(res.data.startswith(b"%PDF-"))

    def test_compress_word_route(self):
        """Verify Word compression route returns valid file and metrics headers."""
        docx_path = FIXTURES_DIR / "huge_image_document.docx"
        with open(docx_path, "rb") as f:
            data = {
                "file": (f, "huge_image_document.docx"),
                "optimize_images": "true"
            }
            res = self.client.post(
                "/api/compress/word",
                data=data,
                content_type="multipart/form-data"
            )

        self.assertEqual(res.status_code, 200)
        self.assertIn("X-Original-Size", res.headers)
        self.assertIn("X-Compressed-Size", res.headers)
        self.assertIn("X-Percent-Saved", res.headers)
        self.assertTrue(res.data.startswith(b"PK\x03\x04"))

    def test_empty_upload_and_invalid_formats(self):
        """Verify edge cases return clean 400 responses without exposing stack traces."""
        # 1. No file part
        res1 = self.client.post("/api/convert/word-to-pdf", data={})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("error", res1.get_json())

        # 2. Uploading a text file to Word-to-PDF
        res2 = self.client.post(
            "/api/convert/word-to-pdf",
            data={"file": (io.BytesIO(b"Hello text"), "test.txt")},
            content_type="multipart/form-data"
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("Unsupported file format", res2.get_json().get("error", ""))

        # 3. Uploading malformed docx
        malformed_docx = FIXTURES_DIR / "malformed.docx"
        with open(malformed_docx, "rb") as f:
            res3 = self.client.post(
                "/api/convert/word-to-pdf",
                data={"file": (f, "malformed.docx")},
                content_type="multipart/form-data"
            )
        self.assertEqual(res3.status_code, 400)
        # Never leak traceback in JSON
        self.assertNotIn("Traceback", res3.get_data(as_text=True))

if __name__ == "__main__":
    unittest.main()
