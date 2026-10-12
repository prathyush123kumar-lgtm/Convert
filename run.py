import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from app import create_app

app = create_app()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    lo_bin = config.find_libreoffice_binary()
    qpdf_bin = config.find_qpdf_binary()

    print(f"\n========================================================")
    print(f" PrivDoc Local Server Running:")
    print(f" -> Localhost Link:      http://localhost:{port}")
    print(f" -> Loopback Link:       http://127.0.0.1:{port}")
    if host == "127.0.0.1":
        print(f" -> Access Mode:         Localhost only (safe default)")
    elif host == "0.0.0.0":
        print(f" -> Access Mode:         LAN access enabled (0.0.0.0)")
    print(f" --------------------------------------------------------")
    print(f" -> LibreOffice Engine:  {'Ready' if lo_bin else 'NOT FOUND (Install LibreOffice for Office to PDF)'}")
    print(f" -> QPDF Engine:         {'Ready' if qpdf_bin else 'NOT FOUND (Using pypdf stream fallback)'}")
    print(f"========================================================\n")
    app.run(host=host, port=port, debug=False)

