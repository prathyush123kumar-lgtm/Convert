# PrivDoc — Privacy-First Document Conversion & Compression Web App

A simple, fast, and secure document utility built with **Python** and **Flask**. Designed for users who want to perform a single document operation, download their file, and leave — with zero accounts, zero tracking, and zero permanent server storage.

---

## 1. Core Purpose & Privacy Architecture

Most document conversion websites store user files on disks, retain documents in database histories, or relay sensitive data to third-party commercial APIs. **PrivDoc** enforces a strict **Zero-Data-Retention** policy:

- **No Permanent Storage**: There is no `uploads/` folder and no database.
- **Isolated Ephemeral Sandboxes**: Each request generates a unique temporary directory via Python's `tempfile.mkdtemp(prefix="privdoc_")` with cryptographically secure random filenames (`secrets.token_hex(16)`). User-supplied file paths are never used on the filesystem.
- **Immediate Disk Purge**: Converted output bytes are loaded into memory and all temporary files and directories on disk are deleted *before or immediately upon* response completion.
- **Cleanup Guarantee**: File purges are enforced in `finally` and context manager blocks, ensuring 100% disk cleanup even when requests fail, raise exceptions, or time out.
- **Zero Content Logging**: Server logs record only anonymous operation types and duration metrics. Document contents, byte streams, extracted text, and personal identifiers are never written to logs.
- **No Third-Party APIs**: All conversions and optimizations run locally on the server using headless LibreOffice, QPDF, `pdf2docx`, and `python-docx`. No third-party cloud services are contacted.
- **Anti-Caching Security Headers**: Every HTTP response sets strict privacy headers:
  ```http
  Cache-Control: no-store, no-cache, must-revalidate, max-age=0, private
  Pragma: no-cache
  Expires: 0
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  ```
- **Security & Resource Limits**: Enforces a strict 50 MB upload limit, 60-second processing timeout, magic byte signature validation, filename sanitization against path traversal, and ZIP decompression bomb safeguards.

---

## 2. Key Features

### 📄 1. Word to PDF (`.docx`, `.doc` → `.pdf`)
- Powered by **LibreOffice** in headless mode (`--headless --convert-to pdf:writer_pdf_Export`).
- Preserves layout, complex tables, headings, embedded vector and raster graphics, and typography.
- Uses dedicated per-request user profile sandboxes (`-env:UserInstallation`) to prevent lock collisions during concurrent conversion requests.

### 📝 2. PDF to Word (`.pdf` → `.docx`)
- Powered by `pdf2docx` (using PyMuPDF and `python-docx`) to reconstruct editable Word documents with paragraphs, tables, and styles.
- **Scanned Document Detection**: Inspects PDF streams before conversion. If a PDF consists of scanned pictures or has no selectable text layer, the system returns a clear `422 Unprocessable Entity` with an actionable **OCR advisory** instead of silently generating an empty or mangled Word document.
- **Encryption Check**: Detects password-protected PDFs and requests password removal upfront.

### 🗜️ 3. Lossless PDF Compression (`.pdf`)
- Powered by **QPDF** (with a lossless `pypdf` stream recompression fallback).
- Performs lossless object stream generation, stream recompression, and unreferenced object removal.
- **Never downsamples images** or introduces lossy compression artifacts.
- **Genuine Savings Reporting**: Measures and returns `X-Original-Size`, `X-Compressed-Size`, and `X-Percent-Saved`. If a file is already optimized, PrivDoc delivers the original unbloated file and clearly informs the user that the document is already optimally structured.

### 📦 4. Word Compression (`.docx`)
- **Safe Mode (Default)**: Recompresses archive entries with maximum Deflate compression (`compresslevel=9`), trimming archive slack safely without touching media or XML fidelity.
- **Optional Embedded-Image Optimization**: When selected, inspects oversized media in `word/media/` and optimizes high-resolution photos with Pillow, showing a transparent advisory that image fidelity may be slightly reduced.

---

## 3. Repository Structure

```
d:\convert\
├── app.py                      # Flask application factory, routes & error handlers
├── config.py                   # Limits, MIME/magic rules, binary auto-detection
├── run.py                      # Application dev launcher
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Project metadata
├── services\                   # Modular business logic
│   ├── __init__.py             # Public exports
│   ├── cleanup.py              # Ephemeral workspace & guaranteed disk cleanup
│   ├── validator.py            # Filetype, magic bytes & size validator
│   ├── word_to_pdf.py          # Headless LibreOffice conversion service
│   ├── pdf_to_word.py          # pdf2docx service with scanned/OCR detection
│   ├── compress_pdf.py         # Lossless QPDF & pypdf compression service
│   └── compress_word.py        # Safe DOCX Deflate & image optimizer
├── static\
│   ├── css\
│   │   └── style.css           # Modern dark/light design system & glassmorphism
│   └── js\
│       └── app.js              # Vanilla JS drag-and-drop, tabs & async flows
├── templates\
│   └── index.html              # Clean semantic HTML5 web interface
└── tests\
    ├── generate_test_fixtures.py # Generates benchmark test documents
    ├── test_services.py        # Unit & integration tests for services
    ├── test_api_routes.py      # End-to-end Flask API route tests
    └── fixtures\               # Generated test files (tables, images, scans)
```

---

## 4. Setup & Installation

### Prerequisites
- **Python 3.10+** (Python 3.12 recommended)
- **LibreOffice** (for Word to PDF)
- **QPDF** (for Lossless PDF Compression)

### Step 1: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Install LibreOffice

- **Windows**:
  ```powershell
  winget install TheDocumentFoundation.LibreOffice --accept-source-agreements --accept-package-agreements
  ```
  *PrivDoc also automatically detects portable installations in `d:\convert\libreoffice\program\soffice.exe` or standard `Program Files`.*
- **Ubuntu / Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y libreoffice-core libreoffice-writer
  ```
- **macOS**:
  ```bash
  brew install --cask libreoffice
  ```
- **Custom Location**:
  Set the `LIBREOFFICE_PATH` environment variable if installed in a non-standard directory:
  ```bash
  export LIBREOFFICE_PATH=/path/to/soffice
  ```

### Step 3: Install QPDF

- **Windows**:
  ```powershell
  winget install QPDF.QPDF --accept-source-agreements --accept-package-agreements
  ```
  *PrivDoc also auto-detects `d:\convert\qpdf-12.4.2-msvc64\bin\qpdf.exe`.*
- **Ubuntu / Debian**:
  ```bash
  sudo apt-get install -y qpdf
  ```
- **macOS**:
  ```bash
  brew install qpdf
  ```
- **Custom Location**:
  Set `QPDF_PATH=/path/to/qpdf` if needed.

---

## 5. Running the Application

### Development Server:
```bash
python run.py
```
Open your browser at `http://127.0.0.1:5000`.

### Production Deployment:
Run with a production WSGI server (such as Gunicorn or Waitress) behind an HTTPS reverse proxy (Nginx or Caddy):

```bash
# Example with Gunicorn (Linux / macOS)
gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"

# Example with Waitress (Windows)
waitress-serve --listen=127.0.0.1:5000 "app:app"
```

**Production Security Recommendations**:
1. **Enforce HTTPS**: Ensure TLS 1.3 is configured at the reverse proxy level to encrypt data in transit.
2. **Reverse Proxy Upload Limits**: Configure `client_max_body_size 50M;` in Nginx to match `MAX_CONTENT_LENGTH`.
3. **Tmpfs Mount**: Mount the server's temporary directory (`/tmp`) as a `tmpfs` (in-memory filesystem) so all temporary files reside in volatile RAM and never touch physical persistent disks.

---

## 6. Running the Test Suite

The test suite validates format conversions, fidelity preservation, scanned document detection, lossless compression calculations, temporary file purging, and security headers:

```bash
# 1. Generate rich test documents (tables, diagrams, scans, malformed files)
python tests/generate_test_fixtures.py

# 2. Run service-level unit & integration tests
python tests/test_services.py

# 3. Run full end-to-end Flask API route tests
python tests/test_api_routes.py
```

### Test Coverage Highlights:
- ✅ **Guaranteed File Cleanup**: Asserts workspace directory and all files cease to exist after successful execution and after simulated unhandled exceptions.
- ✅ **Word to PDF Fidelity**: Verifies multi-row tables, headers, footers, headings, and images convert cleanly to selectable PDF text.
- ✅ **PDF to Word Text Mode**: Confirms reconstruction of editable Word document tables and paragraphs.
- ✅ **Scanned Document Detection**: Verifies pure-raster PDF scans trigger `ScannedDocumentError` with actionable OCR instructions.
- ✅ **Lossless PDF Compression**: Asserts original vs compressed size calculations, ensuring files never bloat.
- ✅ **Word Archive & Media Optimizer**: Asserts safe Deflate compression and verifies embedded image shrinking with Pillow.
- ✅ **API Security & Headers**: Confirms `no-store` cache headers, sanitization of malicious paths (`../../`), rejection of empty files, and absence of internal stack traces in JSON error payloads.

---

## 7. Quality Boundaries & Realistic Limitations

- **Formatting Fidelity**: Word to PDF and PDF to Word rely on standard OpenXML and PDF specifications. Highly exotic third-party fonts, proprietary ActiveX controls, or complex VBA macros cannot be guaranteed to render identically across platforms.
- **Scanned Documents**: pdf2docx requires text streams. Image-only scans must be processed with an OCR tool before conversion.
- **Lossless Compression Limits**: Modern PDF documents containing already compressed assets (e.g. pre-compressed JPEGs) cannot be reduced losslessly without image downsampling. PrivDoc will not artificially degrade image quality in lossless mode.
