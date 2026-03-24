from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app_metadata import (
    APP_ARCHIVE_ASSET_NAME,
    APP_EXE_NAME,
    APP_INSTALL_DIRNAME,
    APP_VERSION,
    INSTALLER_EXE_NAME,
    LAUNCHER_EXE_NAME,
    LOCAL_RELEASE_MANIFEST_NAME,
    PORTABLE_ARCHIVE_ASSET_NAME,
    RELEASE_MANIFEST_ASSET_NAME,
    RUNTIME_ARCHIVE_ASSET_NAME,
)

ROOT_DIR = Path(__file__).resolve().parent
BUILD_ROOT = ROOT_DIR / "build_release"
DIST_ROOT = ROOT_DIR / "dist_release"
RELEASE_ROOT = ROOT_DIR / "release"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build modular Windows release assets.")
    parser.add_argument("--python-cmd", default=sys.executable)
    parser.add_argument("--tag", default=f"v{APP_VERSION}")
    parser.add_argument("--runtime-version", default=None)
    parser.add_argument("--mode", choices=("full", "app-only"), default="full")
    args = parser.parse_args()

    runtime_version = args.runtime_version or default_runtime_version()

    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    shutil.rmtree(DIST_ROOT, ignore_errors=True)
    shutil.rmtree(RELEASE_ROOT, ignore_errors=True)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)

    build_application(args.python_cmd)
    if args.mode == "full":
        build_launcher(args.python_cmd)
    manifest = package_release_assets(tag=args.tag, runtime_version=runtime_version, mode=args.mode)
    write_manifest(manifest, include_portable_layout=args.mode == "full")
    if args.mode == "full":
        build_portable_bundle()
        build_installer(args.python_cmd)
    print(f"Release assets created in: {RELEASE_ROOT}")
    return 0


def default_runtime_version() -> str:
    version = f"py{sys.version_info.major}{sys.version_info.minor}"
    try:
        import PySide6  # type: ignore

        version += f"-pyside6-{PySide6.__version__}"
    except Exception:
        version += "-pyside6-unknown"
    return version


def build_launcher(python_cmd: str) -> None:
    launcher_dist = DIST_ROOT / "launcher"
    launcher_build = BUILD_ROOT / "launcher"
    launcher_spec = BUILD_ROOT / "spec_launcher"
    launcher_dist.mkdir(parents=True, exist_ok=True)
    launcher_build.mkdir(parents=True, exist_ok=True)
    launcher_spec.mkdir(parents=True, exist_ok=True)

    run(
        [
            python_cmd,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            Path(LAUNCHER_EXE_NAME).stem,
            "--distpath",
            str(launcher_dist),
            "--workpath",
            str(launcher_build),
            "--specpath",
            str(launcher_spec),
            "launcher.py",
        ]
    )


def build_application(python_cmd: str) -> None:
    app_dist = DIST_ROOT / "app"
    app_build = BUILD_ROOT / "app"
    app_spec = BUILD_ROOT / "spec_app"
    app_dist.mkdir(parents=True, exist_ok=True)
    app_build.mkdir(parents=True, exist_ok=True)
    app_spec.mkdir(parents=True, exist_ok=True)

    icon_path = ROOT_DIR / "planner_icon.ico"
    command = [
        python_cmd,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        Path(APP_EXE_NAME).stem,
        "--distpath",
        str(app_dist),
        "--workpath",
        str(app_build),
        "--specpath",
        str(app_spec),
    ]
    if icon_path.exists():
        command.extend(["--icon", str(icon_path)])
    command.append("app.py")
    run(command)


def package_release_assets(*, tag: str, runtime_version: str, mode: str) -> dict:
    app_dir = DIST_ROOT / "app" / Path(APP_EXE_NAME).stem
    app_exe = app_dir / APP_EXE_NAME
    runtime_dir = app_dir / "_internal"

    if not app_exe.exists():
        raise FileNotFoundError(app_exe)
    if not runtime_dir.exists():
        raise FileNotFoundError(runtime_dir)

    if mode == "full":
        launcher_exe = DIST_ROOT / "launcher" / LAUNCHER_EXE_NAME
        if not launcher_exe.exists():
            raise FileNotFoundError(launcher_exe)
        shutil.copy2(launcher_exe, RELEASE_ROOT / LAUNCHER_EXE_NAME)
    build_zip(RELEASE_ROOT / APP_ARCHIVE_ASSET_NAME, [(app_exe, Path(APP_EXE_NAME))])
    runtime_files = [(path, path.relative_to(app_dir)) for path in sorted(runtime_dir.rglob("*")) if path.is_file()]
    build_zip(RELEASE_ROOT / RUNTIME_ARCHIVE_ASSET_NAME, runtime_files)

    return {
        "release": {
            "tag": tag,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": mode,
        },
        "app": {
            "version": APP_VERSION,
            "asset_name": APP_ARCHIVE_ASSET_NAME,
            "archive_sha256": sha256_file(RELEASE_ROOT / APP_ARCHIVE_ASSET_NAME),
            "files": [file_manifest(app_exe, app_dir)],
        },
        "runtime": {
            "version": runtime_version,
            "asset_name": RUNTIME_ARCHIVE_ASSET_NAME,
            "archive_sha256": sha256_file(RELEASE_ROOT / RUNTIME_ARCHIVE_ASSET_NAME),
            "files": [file_manifest(path, app_dir) for path, _ in runtime_files],
        },
    }


def write_manifest(manifest: dict, *, include_portable_layout: bool) -> None:
    manifest_path = RELEASE_ROOT / RELEASE_MANIFEST_ASSET_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    if not include_portable_layout:
        return

    current_dir = RELEASE_ROOT / APP_INSTALL_DIRNAME
    current_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DIST_ROOT / "app" / Path(APP_EXE_NAME).stem / APP_EXE_NAME, current_dir / APP_EXE_NAME)
    shutil.copytree(
        DIST_ROOT / "app" / Path(APP_EXE_NAME).stem / "_internal",
        current_dir / "_internal",
        dirs_exist_ok=True,
    )
    (current_dir / LOCAL_RELEASE_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def build_portable_bundle() -> None:
    portable_entries = [
        (RELEASE_ROOT / LAUNCHER_EXE_NAME, Path(LAUNCHER_EXE_NAME)),
    ]
    current_root = RELEASE_ROOT / APP_INSTALL_DIRNAME
    portable_entries.extend(
        (path, path.relative_to(RELEASE_ROOT))
        for path in sorted(current_root.rglob("*"))
        if path.is_file()
    )
    build_zip(RELEASE_ROOT / PORTABLE_ARCHIVE_ASSET_NAME, portable_entries)


def build_installer(python_cmd: str) -> None:
    installer_dist = DIST_ROOT / "installer"
    installer_build = BUILD_ROOT / "installer"
    installer_spec = BUILD_ROOT / "spec_installer"
    installer_dist.mkdir(parents=True, exist_ok=True)
    installer_build.mkdir(parents=True, exist_ok=True)
    installer_spec.mkdir(parents=True, exist_ok=True)

    portable_archive = RELEASE_ROOT / PORTABLE_ARCHIVE_ASSET_NAME
    if not portable_archive.exists():
        raise FileNotFoundError(portable_archive)

    command = [
        python_cmd,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        Path(INSTALLER_EXE_NAME).stem,
        "--distpath",
        str(installer_dist),
        "--workpath",
        str(installer_build),
        "--specpath",
        str(installer_spec),
        "--add-data",
        f"{portable_archive}{os.pathsep}.",
        "installer.py",
    ]
    run(command)
    shutil.copy2(installer_dist / INSTALLER_EXE_NAME, RELEASE_ROOT / INSTALLER_EXE_NAME)


def build_zip(destination: Path, entries: list[tuple[Path, Path]]) -> None:
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for src_path, arc_path in entries:
            zf.write(src_path, arcname=arc_path.as_posix())


def file_manifest(file_path: Path, base_dir: Path) -> dict:
    stat = file_path.stat()
    return {
        "path": file_path.relative_to(base_dir).as_posix(),
        "sha256": sha256_file(file_path),
        "size": stat.st_size,
    }


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT_DIR, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
