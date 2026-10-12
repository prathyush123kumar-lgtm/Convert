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
    convert_office_to_pdf,
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
    merge_pdf_documents,
    split_pdf_document,
    PDFMergeError,
    PDFSplitError,
    sanitize_document_metadata,
    MetadataScrubberError,
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
        response.headers["Access-Control-Expose-Headers"] = (
            "X-Original-Size, X-Compressed-Size, X-Saved-Bytes, X-Percent-Saved, X-Is-Reduced, "
            "X-Files-Merged, X-Total-Pages, X-Original-Pages, X-Extracted-Pages, "
            "X-Fields-Scrubbed, X-Images-Sanitized"
        )
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        max_mb = config.MAX_CONTENT_LENGTH // (1024 * 1024)
        return jsonify({"error": f"File exceeds the maximum upload limit of {max_mb} MB."}), 413

    @app.errorhandler(ValidationError)
    @app.errorhandler(PDFMergeError)
    @app.errorhandler(PDFSplitError)
    @app.errorhandler(MetadataScrubberError)
    def handle_client_validation_error(e):
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

    @app.route("/favicon.ico")
    def favicon():
        return Response(status=204)


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

    # ---------------- 1. Office to PDF (Word, Excel, PowerPoint) ----------------
    @app.route("/api/convert/word-to-pdf", methods=["POST"])
    @app.route("/api/convert/office-to-pdf", methods=["POST"])
    def route_office_to_pdf():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="office")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}.pdf"

        # Strictly isolated ephemeral workspace
        with EphemeralWorkspace(prefix="priv_off2p_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".pdf")

            uploaded_file.save(str(input_path))
            convert_office_to_pdf(input_path, output_path, ws)

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
            convert_pdf_to_word(input_path, output_path)

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

        strong_mode = request.form.get("strong_mode", "false").lower() == "true"

        with EphemeralWorkspace(prefix="priv_cmp_pdf_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".pdf")

            uploaded_file.save(str(input_path))
            stats = compress_pdf_lossless(input_path, output_path, ws, strong_mode=strong_mode)

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
        return response

    # ---------------- 5. Merge PDFs ----------------
    @app.route("/api/pdf/merge", methods=["POST"])
    def route_merge_pdf():
        uploaded_files = request.files.getlist("files")
        if not uploaded_files or len(uploaded_files) == 0:
            uploaded_files = request.files.getlist("file")

        if not uploaded_files or len(uploaded_files) < 2:
            return jsonify({"error": "Please select at least 2 PDF files to merge."}), 400

        with EphemeralWorkspace(prefix="priv_merge_") as ws:
            saved_paths = []
            for i, f in enumerate(uploaded_files):
                validate_upload(f, expected_type="pdf")
                in_path = ws.secure_path(suffix=f"_{i}.pdf")
                f.save(str(in_path))
                saved_paths.append(in_path)

            output_path = ws.secure_path(suffix="_merged.pdf")
            stats = merge_pdf_documents(saved_paths, output_path)

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        response = make_response(output_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = 'attachment; filename="merged_document.pdf"'
        response.headers["X-Files-Merged"] = str(stats["files_merged"])
        response.headers["X-Total-Pages"] = str(stats["total_pages"])
        return response

    # ---------------- 6. Split PDF / Extract Pages ----------------
    @app.route("/api/pdf/split", methods=["POST"])
    def route_split_pdf():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        page_range = request.form.get("pages", "").strip()
        if not page_range:
            return jsonify({"error": "Please provide the page numbers to extract (e.g. 1-3, 5)."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="pdf")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}_extracted.pdf"

        with EphemeralWorkspace(prefix="priv_split_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=".pdf")

            uploaded_file.save(str(input_path))
            stats = split_pdf_document(input_path, output_path, page_range)

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        response = make_response(output_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="{out_name}"'
        response.headers["X-Original-Pages"] = str(stats["original_pages"])
        response.headers["X-Extracted-Pages"] = str(stats["extracted_pages"])
        return response

    # ---------------- 7. Metadata Scrubber (Privacy Sanitizer) ----------------
    @app.route("/api/sanitize/metadata", methods=["POST"])
    def route_sanitize_metadata():
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        ext = validate_upload(uploaded_file, expected_type="sanitizable")
        clean_name = sanitize_filename(uploaded_file.filename, default="document")
        out_name = f"{Path(clean_name).stem}_sanitized.{ext}"

        with EphemeralWorkspace(prefix="priv_scrub_") as ws:
            input_path = ws.secure_path(suffix=f".{ext}")
            output_path = ws.secure_path(suffix=f".{ext}")

            uploaded_file.save(str(input_path))
            stats = sanitize_document_metadata(input_path, output_path, ext)

            with open(output_path, "rb") as f:
                output_bytes = f.read()

        content_type = "application/pdf" if ext == "pdf" else "application/octet-stream"
        if ext == "docx":
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == "xlsx":
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif ext == "pptx":
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

        response = make_response(output_bytes)
        response.headers["Content-Type"] = content_type
        response.headers["Content-Disposition"] = f'attachment; filename="{out_name}"'
        response.headers["X-Fields-Scrubbed"] = str(stats["fields_scrubbed"])
        response.headers["X-Images-Sanitized"] = str(stats["images_sanitized"])
        response.headers["X-Original-Size"] = str(stats["original_size"])
        response.headers["X-Sanitized-Size"] = str(stats["sanitized_size"])
        return response

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"\n========================================================")
    print(f" PrivDoc Local Server Running:")
    print(f" -> Localhost Link:      http://localhost:{port}")
    print(f" -> Loopback Link:       http://127.0.0.1:{port}")
    if host == "127.0.0.1":
        print(f" -> Access Mode:         Localhost only (safe default)")
    elif host == "0.0.0.0":
        print(f" -> Access Mode:         LAN access enabled (0.0.0.0)")
    print(f"========================================================\n")
    app.run(host=host, port=port, debug=False)
