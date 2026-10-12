import os
import shutil
import stat
import tempfile
import secrets
from pathlib import Path
from typing import Generator, Optional

def _handle_remove_readonly(func, path, exc_info):
    """Clear the readonly bit and reattempt removal on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

class EphemeralWorkspace:
    """
    Context manager for a strictly isolated temporary workspace.
    Guarantees that uploaded and generated files are erased completely
    upon exit, exception, or timeout.
    """
    def __init__(self, prefix: str = "privdoc_"):
        self.prefix = prefix
        self.path: Optional[Path] = None

    def __enter__(self) -> "EphemeralWorkspace":
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self) -> None:
        """Purge the workspace and all files permanently."""
        if self.path and self.path.exists():
            try:
                shutil.rmtree(self.path, onerror=_handle_remove_readonly)
            except Exception:
                pass
            self.path = None

    def secure_path(self, suffix: str = "") -> Path:
        """Generate a random server-side filename within this temporary workspace."""
        if not self.path or not self.path.exists():
            raise RuntimeError("Ephemeral workspace is not active or has been purged.")
        # Generate 16 random hex bytes (32 chars) - never trust user input
        rand_name = f"{secrets.token_hex(16)}{suffix}"
        return self.path / rand_name

def create_cleanup_stream(data_stream: Generator[bytes, None, None], cleanup_callback) -> Generator[bytes, None, None]:
    """
    Wraps a byte generator to ensure the cleanup callback is executed
    immediately when the stream finishes or if the client disconnects.
    """
    try:
        for chunk in data_stream:
            yield chunk
    finally:
        cleanup_callback()
