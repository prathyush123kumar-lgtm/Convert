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

### 📄 1. Office to PDF (`.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.ppt` → `.pdf`)
- Powered by **LibreOffice** in headless mode (`--headless --convert-to pdf`).
- Converts Word documents, Excel spreadsheets, and PowerPoint presentations with preserved layout, complex tables, embedded charts, vector graphics, and typography.
- Uses dedicated per-request user profile sandboxes (`-env:UserInstallation`) to prevent lock collisions during concurrent conversion requests.

### 📝 2. PDF to Word (`.pdf` → `.docx`)
- Powered by `pdf2docx` (using PyMuPDF and `python-docx`) to reconstruct editable Word documents with paragraphs, tables, and styles.
- **Scanned Document Detection**: Inspects PDF streams before conversion. If a PDF consists of scanned pictures or has no selectable text layer, the system returns a clear `422 Unprocessable Entity` with an actionable **OCR advisory** instead of silently generating an empty or mangled Word document.
- **Encryption Check**: Detects password-protected PDFs and requests password removal upfront.

### 📚 3. PDF Merge & Split / Page Extraction (`.pdf`)
- Powered by `pypdf`.
- **Merge**: Combine 2 or more PDF documents into a single ordered document in isolated ephemeral memory.
- **Split / Extract Pages**: Extract custom page ranges (e.g. `1-3, 5` or `all`) into a clean, standalone PDF.

### 🛡️ 4. Document Metadata & Author Scrubber (Privacy Sanitizer)
- Scrubs identifying tracking tags from **PDF, DOCX, XLSX, and PPTX** documents:
  - Wipes author names, organization/company tags, and manager fields.
  - Clears creation, modification, and revision timestamps.
  - Purges XML tracking packets (`/Metadata`) and custom user properties.
  - Strips GPS location and camera EXIF metadata from embedded JPEG/PNG photos.

### 🗜️ 5. Lossless PDF Compression (`.pdf`)
- Powered by **QPDF** (with a lossless `pypdf` stream recompression fallback).
- Performs lossless object stream generation, stream recompression, and unreferenced object removal.
- **Never downsamples images** in default mode. Includes an optional strong compression mode for heavy photographic documents.
- **Genuine Savings Reporting**: Measures and returns `X-Original-Size`, `X-Compressed-Size`, and `X-Percent-Saved`.

### 📦 6. Word Compression (`.docx`)
- **Safe Mode (Default)**: Recompresses archive entries with maximum Deflate compression (`compresslevel=9`), trimming archive slack safely without touching media or XML fidelity.
- **Optional Embedded-Image Optimization**: When selected, inspects oversized media in `word/media/` and optimizes high-resolution photos with Pillow.


---

## 3. Repository Structure

```
d:\convert\
├── app.py                      # Flask application factory, routes & error handlers
├── config.py                   # Limits, MIME/magic rules, binary auto-detection
├── run.py                      # Application dev launcher (defaults to 127.0.0.1:5000)
├── start_privdoc.bat           # Windows quick-start launcher
├── requirements.txt            # Core runtime Python dependencies
├── requirements-dev.txt        # Development & test-fixture dependencies
├── services\                   # Modular business logic
│   ├── __init__.py             # Public exports
│   ├── cleanup.py              # Ephemeral workspace & guaranteed disk cleanup
│   ├── validator.py            # Filetype, magic bytes & size validator
│   ├── office_to_pdf.py        # Headless LibreOffice conversion service (Word, Excel, PPT)
│   ├── pdf_to_word.py          # pdf2docx service with scanned/OCR detection
│   ├── pdf_tools.py            # PDF merge and page extraction/split service
│   ├── compress_pdf.py         # Lossless QPDF & pypdf compression service
│   ├── compress_word.py        # Safe DOCX Deflate & image optimizer
│   └── metadata_scrubber.py    # Author, tracking & EXIF metadata sanitizer
├── static\
│   ├── css\
│   │   └── style.css           # Privacy-first design system with native system fonts
│   └── js\
│       └── app.js              # Vanilla JS drag-and-drop, tabs & async flows
├── templates\
│   └── index.html              # Clean semantic HTML5 web interface (zero external CDN calls)
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
- **LibreOffice** (Required for Office to PDF: `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.ppt`)
- **QPDF** (Required for Lossless PDF Compression; falls back to `pypdf` if missing)

### Step 1: Install Python Dependencies

**Core Runtime (Production):**
```bash
pip install -r requirements.txt
```

**Development & Test Fixture Tools (Optional):**
To generate synthetic test documents (`openpyxl`, `python-pptx`), install the development manifest:
```bash
pip install -r requirements-dev.txt
```

### Step 2: Install LibreOffice

- **Windows**:
  ```powershell
  winget install TheDocumentFoundation.LibreOffice --accept-source-agreements --accept-package-agreements
  ```
  *PrivDoc also automatically detects portable installations in `d:\convert\libreoffice\program\soffice.exe` or standard `Program Files`.*
- **Ubuntu / Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress
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

### Windows Quick Launch
Double-click `start_privdoc.bat` in the project root. This opens your browser to `http://localhost:5000` and starts the local server.

### Command Line / Development Server
```bash
python run.py
```
Open your browser at `http://127.0.0.1:5000` or `http://localhost:5000`.

### Safe Localhost-Only Default & LAN Sharing
By default, PrivDoc binds strictly to `127.0.0.1` (localhost) to ensure other devices on your Wi-Fi or local network cannot access the converter or submit documents.

**To explicitly enable Local Area Network (LAN) access:**
Set the `HOST` environment variable to `0.0.0.0`:
* **Windows (PowerShell)**:
  ```powershell
  $env:HOST="0.0.0.0"; python run.py
  ```
* **Windows (Command Prompt)**:
  ```cmd
  set HOST=0.0.0.0 && python run.py
  ```
* **Linux / macOS**:
  ```bash
  HOST=0.0.0.0 python run.py
  ```

### Production Deployment
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
# Run full automated test suite (all unit and integration tests)
python -m unittest discover -s tests

# (Optional) Regenerate synthetic test documents
python tests/generate_test_fixtures.py
```

### Test Coverage Highlights:
- ✅ **Guaranteed File Cleanup**: Asserts workspace directory and all files cease to exist after successful execution and after simulated unhandled exceptions.
- ✅ **Office to PDF Fidelity**: Verifies Word, Excel, and PowerPoint documents convert cleanly to selectable PDF text.
- ✅ **PDF to Word Text Mode**: Confirms reconstruction of editable Word document tables and paragraphs.
- ✅ **Scanned Document Detection**: Verifies pure-raster PDF scans trigger `ScannedDocumentError` with actionable OCR instructions.
- ✅ **Lossless PDF Compression**: Asserts original vs compressed size calculations, ensuring files never bloat.
- ✅ **Word Archive & Media Optimizer**: Asserts safe Deflate compression and verifies embedded image shrinking with Pillow.
- ✅ **Metadata Sanitizer**: Asserts removal of author properties, XML tracking packets, and image EXIF GPS metadata.
- ✅ **API Security & Headers**: Confirms `no-store` cache headers, sanitization of malicious paths (`../../`), rejection of empty files, and absence of internal stack traces in JSON error payloads.

---

## 7. Quality Boundaries & Realistic Limitations

- **Formatting Fidelity**: Word to PDF and PDF to Word rely on standard OpenXML and PDF specifications. Highly exotic third-party fonts not installed on the server will trigger font substitution. Complex Excel print pagination without pre-defined print areas may wrap across multiple pages.
- **Scanned Documents**: `pdf2docx` requires text streams. Image-only scans are detected upfront and rejected with an OCR recommendation. PrivDoc does not bundle a heavy OCR engine by default.
- **Lossless Compression Limits**: Modern PDF documents containing already compressed assets (e.g. pre-compressed JPEGs) cannot be reduced losslessly without image downsampling. PrivDoc will not artificially degrade image quality in lossless mode and prevents bloating by returning the original file if no reduction is achieved.
- **Metadata Sanitization Scope**: The metadata scrubber clears standard document properties (author, title, revision, timestamps), application/custom XML properties, and camera EXIF metadata in embedded photos. It **does not** redact inline text, inline comments, tracked changes in the document body (`w:ins`/`w:del`), footnotes, or macros.
- **Network Privacy**: PrivDoc requires zero external cloud APIs. External Google Fonts CDN requests have been removed, rendering using native system font stacks (`system-ui`, `ui-monospace`) with zero third-party browser network connections.

