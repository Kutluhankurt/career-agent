"""Build a standalone `career` executable for the current OS with PyInstaller (roadmap §49).

    uv run --with pyinstaller python scripts/build_binary.py

Output: dist/career (dist/career.exe on Windows). Build on each target OS/architecture:
PyInstaller does not cross-compile. Build the dashboard first (npm run build in dashboard/)
so the UI is bundled.
"""

import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "career" / "server" / "static"


def main() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller is missing: uv run --with pyinstaller python scripts/build_binary.py")
    entry = ROOT / "build" / "career_entry.py"
    entry.parent.mkdir(exist_ok=True)
    entry.write_text("from career.cli.main import app\n\nif __name__ == '__main__':\n    app()\n")
    sep = ";" if platform.system() == "Windows" else ":"
    args = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--name", "career", "--clean", "--noconfirm",
        "--paths", str(ROOT / "src"),
        "--collect-submodules", "career",
        "--collect-submodules", "uvicorn",
        "--collect-data", "docx",
        "--hidden-import", "keyring.backends",
        "--collect-submodules", "keyring.backends",
        str(entry),
    ]
    if (STATIC / "index.html").exists():
        args[3:3] = ["--add-data", f"{STATIC}{sep}career/server/static"]
    else:
        print("warning: dashboard not built; the binary will serve the API only")
    subprocess.run(args, check=True, cwd=ROOT)
    out = ROOT / "dist" / ("career.exe" if platform.system() == "Windows" else "career")
    print(f"Built {out} ({out.stat().st_size / 1e6:.1f} MB) for {platform.system()} {platform.machine()}")


if __name__ == "__main__":
    main()
