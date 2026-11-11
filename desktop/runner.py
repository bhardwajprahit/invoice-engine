"""PyInstaller entry point for the desktop API and OCR worker processes."""

import sys
from pathlib import Path

# In development, application modules live at the repository root. In the
# packaged one-file executable, PyInstaller also places bundled modules on
# sys.path; this keeps the same entry point usable in both environments.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Expected api or worker role")

    role = sys.argv[1]
    if role == "api":
        import uvicorn
        import api  # Static import so PyInstaller includes api.py in the bundle.

        port = int(sys.argv[2])
        uvicorn.run(api.app, host="127.0.0.1", port=port, workers=1)
    elif role == "worker":
        import worker

        worker.run_worker()
    else:
        raise SystemExit("Unknown backend role")


if __name__ == "__main__":
    main()
