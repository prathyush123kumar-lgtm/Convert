import io
import os
import logging
from pathlib import Path
from flask import Flask, request, jsonify, render_template, Response, make_response
from werkzeug.exceptions import RequestEntityTooLarge

import config
from services import (
    EphemeralWorkspace,
    validate_upload,
    sanitize_filename,
    ValidationError,
    convert_word_to_pdf,
    ConversionError,
    ConversionTimeoutError,
    convert_pdf_to_word,
    ScannedDocumentError,
    PasswordProtectedError,
    PDFToWordError,
    compress_pdf_lossless,
    PDFCompressionError,
    compress_word_document,
    WordCompressionError,
)

# Configure anonymous, privacy-preserving logging
# Never log file contents, raw payloads, or user personal identifiers
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
logger = logging.getLogger("privdoc")

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config["SECRET_KEY"] = os.urandom(32)

    @app.after_request
    def set_security_and_privacy_headers(response: Response) -> Response:
        """
        Enforce strict privacy headers across all responses.
        Prevents browser caching, intermediate proxy caching, and clickjacking.
        """
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        max_mb = config.MAX_CONTENT_LENGTH // (1024 * 1024)
        return jsonify({"error": f"File exceeds the maximum upload limit of {max_mb} MB."}), 413

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(ScannedDocumentError)
    def handle_scanned_doc_error(e):
        return jsonify({
            "error": str(e),
            "code": "SCANNED_DOCUMENT",
            "ocr_required": True
        }), 422

    @app.errorhandler(PasswordProtectedError)
    def handle_password_error(e):
        return jsonify({
            "error": str(e),
            "code": "PASSWORD_PROTECTED"
        }), 422

    @app.errorhandler(ConversionTimeoutError)
    def handle_timeout_error(e):
        logger.warning("Conversion timeout occurred.")
        return jsonify({"error": str(e), "code": "TIMEOUT"}), 504

    @app.errorhandler(ConversionError)
    @app.errorhandler(PDFToWordError)
    @app.errorhandler(PDFCompressionError)
    @app.errorhandler(WordCompressionError)
    def handle_conversion_error(e):
        logger.error(f"Processing error: {str(e)}")
        return jsonify({"error": str(e)}), 500

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        # Prevent stack trace leakage to the client
        logger.error("Unhandled server exception encountered.")
        return jsonify({"error": "An internal error occurred during processing. Please try again."}), 500

    # ---------------- UI Route ----------------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/system-status")
    def system_status():
        """Check availability of LibreOffice and QPDF binaries."""
        has_lo = config.find_libreoffice_binary() is not None
        has_qpdf = config.find_qpdf_binary() is not None
        return jsonify({
            "status": "ready",
            "libreoffice_available": has_lo,
            "qpdf_available": has_qpdf,
            "max_file_size_mb": config.MAX_CONTENT_LENGTH // (1024 * 1024),
            "timeout_seconds": config.CONVERSION_TIMEOUT_SECONDS
        })

    # ---------------- 1. Word to PDF ----------------
    @app.route("/api/convert/word-to-pdf", methods=["POST"])
    def route_word_to_pdf():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="docx")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}.pdf"

        # Strictly isolated ephemeral workspace
        with EphemeralWorkspace(prefix="priv_w2p_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".pdf")

            uploaded_file.save(str(input_path))
            convert_word_to_pdf(input_path, output_path, ws)

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        # Workspace is completely purged from disk before response is sent
        response = make_response(output_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{out_name}"'
        return response

    # ---------------- 2. PDF to Word ----------------
    @app.route("/api/convert/pdf-to-word", methods=["POST"])
    def route_pdf_to_word():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="pdf")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}.docx"

        with EphemeralWorkspace(prefix="priv_p2w_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".docx")

            uploaded_file.save(str(input_path))
            convert_pdf_to_word(input_path, output_path, ws)

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        response = make_response(output_bytes)
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        response.headers["Content-Disposition"] = f'attachment; filename="{out_name}"'
        return response

    # ---------------- 3. Compress PDF ----------------
    @app.route("/api/compress/pdf", methods=["POST"])
    def route_compress_pdf():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="pdf")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}_compressed.pdf"

        with EphemeralWorkspace(prefix="priv_cmp_pdf_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".pdf")

            uploaded_file.save(str(input_path))
            stats = compress_pdf_lossless(input_path, output_path, ws)

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        response = make_response(output_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{out_name}"'
        response.headers["X-Original-Size"] = str(stats["original_size"])
        response.headers["X-Compressed-Size"] = str(stats["compressed_size"])
        response.headers["X-Saved-Bytes"] = str(stats["saved_bytes"])
        response.headers["X-Percent-Saved"] = str(stats["percent_saved"])
        response.headers["X-Is-Reduced"] = "1" if stats["is_reduced"] else "0"
        response.headers["Access-Control-Expose-Headers"] = (
            "X-Original-Size, X-Compressed-Size, X-Saved-Bytes, X-Percent-Saved, X-Is-Reduced"
        )
        return response

    # ---------------- 4. Compress Word ----------------
    @app.route("/api/compress/word", methods=["POST"])
    def route_compress_word():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="docx")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}_compressed.docx"

        optimize_images = request.form.get("optimize_images", "false").lower() == "true"

        with EphemeralWorkspace(prefix="priv_cmp_doc_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".docx")

            uploaded_file.save(str(input_path))
            stats = compress_word_document(
                input_path,
                output_path,
                ws,
                optimize_images=optimize_images
            )

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        response = make_response(output_bytes)
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        response.headers["Content-Disposition"] = f'attachment; filename="{out_name}"'
        response.headers["X-Original-Size"] = str(stats["original_size"])
        response.headers["X-Compressed-Size"] = str(stats["compressed_size"])
        response.headers["X-Saved-Bytes"] = str(stats["saved_bytes"])
        response.headers["X-Percent-Saved"] = str(stats["percent_saved"])
        response.headers["X-Is-Reduced"] = "1" if stats["is_reduced"] else "0"
        response.headers["Access-Control-Expose-Headers"] = (
            "X-Original-Size, X-Compressed-Size, X-Saved-Bytes, X-Percent-Saved, X-Is-Reduced"
        )
        return response

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
