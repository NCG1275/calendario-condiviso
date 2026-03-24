from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

from app_metadata import APP_NAME, LAUNCHER_EXE_NAME

PORTABLE_ARCHIVE_NAME = "planner-portable-win64.zip"


def bundled_archive_path() -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    archive_path = base_dir / PORTABLE_ARCHIVE_NAME
    if not archive_path.exists():
        raise FileNotFoundError(f"Archivio installazione non trovato: {archive_path}")
    return archive_path


def choose_install_dir() -> Path | None:
    root = Tk()
    root.withdraw()
    root.update()
    selected = filedialog.askdirectory(
        title=f"Seleziona la cartella di installazione di {APP_NAME}",
        mustexist=False,
    )
    root.destroy()
    if not selected:
        return None
    return Path(selected).expanduser().resolve()


def extract_portable_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("Archivio di installazione non valido.")
        zf.extractall(destination)


def main() -> int:
    try:
        archive_path = bundled_archive_path()
    except Exception as exc:
        messagebox.showerror(APP_NAME, str(exc))
        return 1

    install_dir = choose_install_dir()
    if install_dir is None:
        return 0

    try:
        extract_portable_archive(archive_path, install_dir)
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"Installazione non riuscita:\n{exc}")
        return 1

    launcher_path = install_dir / LAUNCHER_EXE_NAME
    message = (
        f"Installazione completata in:\n{install_dir}\n\n"
        f"Per avviare l'app usa:\n{launcher_path}"
    )
    messagebox.showinfo(APP_NAME, message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
