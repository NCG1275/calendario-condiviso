from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path

from app_metadata import APP_NAME
from updater import UpdateError, ensure_app_install


def show_error(message: str) -> None:
    if sys.platform.startswith("win"):
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        return
    print(message, file=sys.stderr)


def main() -> int:
    install_root = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    try:
        app_executable = ensure_app_install(install_root)
    except UpdateError as exc:
        show_error(str(exc))
        return 1

    process = subprocess.Popen(
        [str(app_executable), *sys.argv[1:]],
        cwd=str(app_executable.parent),
    )
    return 0 if process.pid else 1


if __name__ == "__main__":
    raise SystemExit(main())
