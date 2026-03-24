from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app_metadata import (
    APP_ARCHIVE_ASSET_NAME,
    APP_EXE_NAME,
    APP_INSTALL_DIRNAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    LOCAL_RELEASE_MANIFEST_NAME,
    RELEASE_MANIFEST_ASSET_NAME,
    RUNTIME_ARCHIVE_ASSET_NAME,
)

USER_AGENT = "planner-turni-updater"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemoteReleaseState:
    manifest: dict[str, Any]
    release_tag: str


def ensure_app_install(install_root: Path) -> Path:
    current_dir = install_root / APP_INSTALL_DIRNAME
    current_dir.mkdir(parents=True, exist_ok=True)

    local_manifest_path = current_dir / LOCAL_RELEASE_MANIFEST_NAME
    local_manifest = _load_json(local_manifest_path)

    remote_state: RemoteReleaseState | None = None
    remote_error: Exception | None = None
    try:
        remote_state = fetch_remote_release_state()
    except Exception as exc:  # pragma: no cover - fallback path
        remote_error = exc

    manifest_for_validation = remote_state.manifest if remote_state is not None else local_manifest
    if manifest_for_validation is None:
        raise UpdateError(
            "Non riesco a leggere una release valida da GitHub e non esiste una copia locale dell'app."
        ) from remote_error

    if remote_state is not None:
        try:
            runtime_is_valid = verify_manifest_files(current_dir, remote_state.manifest.get("runtime", {}))
            app_is_valid = verify_manifest_files(current_dir, remote_state.manifest.get("app", {}))
            runtime_version = _manifest_version(local_manifest, "runtime")
            app_version = _manifest_version(local_manifest, "app")
            remote_runtime_version = _manifest_version(remote_state.manifest, "runtime")
            remote_app_version = _manifest_version(remote_state.manifest, "app")

            if runtime_version != remote_runtime_version or not runtime_is_valid:
                _install_component_archive(
                    current_dir=current_dir,
                    component_name="runtime",
                    component_manifest=remote_state.manifest["runtime"],
                    expected_asset_name=RUNTIME_ARCHIVE_ASSET_NAME,
                    replace_mode="dir",
                )

            if app_version != remote_app_version or not app_is_valid:
                _install_component_archive(
                    current_dir=current_dir,
                    component_name="app",
                    component_manifest=remote_state.manifest["app"],
                    expected_asset_name=APP_ARCHIVE_ASSET_NAME,
                    replace_mode="file",
                )

            _write_json(local_manifest_path, remote_state.manifest)
            manifest_for_validation = remote_state.manifest
        except Exception as exc:
            if local_manifest is None:
                raise
            manifest_for_validation = local_manifest
            if not verify_manifest_files(current_dir, local_manifest.get("runtime", {})):
                raise UpdateError("Aggiornamento fallito e runtime locale non piu' valido.") from exc
            if not verify_manifest_files(current_dir, local_manifest.get("app", {})):
                raise UpdateError("Aggiornamento fallito e app locale non piu' valida.") from exc

    if not verify_manifest_files(current_dir, manifest_for_validation.get("runtime", {})):
        raise UpdateError("Le dipendenze locali non sono integre e non sono riuscito a ripristinarle.")
    if not verify_manifest_files(current_dir, manifest_for_validation.get("app", {})):
        raise UpdateError("L'eseguibile locale non e' integro e non sono riuscito a ripristinarlo.")

    exe_path = current_dir / APP_EXE_NAME
    if not exe_path.exists():
        raise UpdateError(f"Eseguibile non trovato: {exe_path}")
    return exe_path


def fetch_remote_release_state(timeout: int = 15) -> RemoteReleaseState:
    release_payload = _download_json(GITHUB_LATEST_RELEASE_API, timeout=timeout)
    assets = release_payload.get("assets", [])
    if not isinstance(assets, list):
        raise UpdateError("La release GitHub non contiene un elenco asset valido.")

    asset_urls = {
        asset.get("name"): asset.get("browser_download_url")
        for asset in assets
        if isinstance(asset, dict)
    }
    manifest_url = asset_urls.get(RELEASE_MANIFEST_ASSET_NAME)
    if not manifest_url:
        raise UpdateError(f"Asset manifest non trovato nella release: {RELEASE_MANIFEST_ASSET_NAME}")

    manifest = _download_json(manifest_url, timeout=timeout)
    _attach_asset_urls(manifest, asset_urls)
    return RemoteReleaseState(
        manifest=manifest,
        release_tag=str(release_payload.get("tag_name", "")).strip(),
    )


def verify_manifest_files(base_dir: Path, component_manifest: dict[str, Any]) -> bool:
    files = component_manifest.get("files", [])
    if not isinstance(files, list) or not files:
        return False

    for file_info in files:
        if not isinstance(file_info, dict):
            return False
        rel_path = str(file_info.get("path", "")).strip()
        expected_sha256 = str(file_info.get("sha256", "")).strip().lower()
        if not rel_path or not expected_sha256:
            return False
        target_path = base_dir / Path(rel_path)
        if not target_path.exists() or not target_path.is_file():
            return False
        if sha256_file(target_path) != expected_sha256:
            return False
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_json(url: str, timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except HTTPError as exc:  # pragma: no cover - network dependent
        raise UpdateError(f"GitHub ha risposto con errore HTTP {exc.code}.") from exc
    except URLError as exc:  # pragma: no cover - network dependent
        raise UpdateError(f"Connessione a GitHub non riuscita: {exc.reason}") from exc

    try:
        data = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise UpdateError("Contenuto JSON non valido ricevuto da GitHub.") from exc
    if not isinstance(data, dict):
        raise UpdateError("La risposta ricevuta da GitHub non ha il formato atteso.")
    return data


def _attach_asset_urls(manifest: dict[str, Any], asset_urls: dict[str, str | None]) -> None:
    for key, asset_name in (("app", APP_ARCHIVE_ASSET_NAME), ("runtime", RUNTIME_ARCHIVE_ASSET_NAME)):
        component = manifest.get(key)
        if not isinstance(component, dict):
            raise UpdateError(f"Manifest non valido: sezione '{key}' mancante.")
        actual_asset_name = str(component.get("asset_name", "")).strip() or asset_name
        asset_url = asset_urls.get(actual_asset_name)
        if not asset_url:
            raise UpdateError(f"Asset non trovato nella release GitHub: {actual_asset_name}")
        component["asset_name"] = actual_asset_name
        component["asset_url"] = asset_url


def _manifest_version(manifest: dict[str, Any] | None, key: str) -> str:
    if not isinstance(manifest, dict):
        return ""
    component = manifest.get(key)
    if not isinstance(component, dict):
        return ""
    return str(component.get("version", "")).strip()


def _install_component_archive(
    *,
    current_dir: Path,
    component_name: str,
    component_manifest: dict[str, Any],
    expected_asset_name: str,
    replace_mode: str,
) -> None:
    asset_name = str(component_manifest.get("asset_name", "")).strip()
    asset_url = str(component_manifest.get("asset_url", "")).strip()
    archive_sha256 = str(component_manifest.get("archive_sha256", "")).strip().lower()
    if not asset_name or asset_name != expected_asset_name:
        raise UpdateError(f"Manifest {component_name} non valido: asset_name atteso '{expected_asset_name}'.")
    if not asset_url or not archive_sha256:
        raise UpdateError(f"Manifest {component_name} non valido: URL o hash archivio mancanti.")

    tmp_root = Path(tempfile.mkdtemp(prefix=f"planner-{component_name}-", dir=current_dir))
    archive_path = tmp_root / asset_name
    extracted_dir = tmp_root / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    try:
        _download_file(asset_url, archive_path)
        if sha256_file(archive_path) != archive_sha256:
            raise UpdateError(f"Hash archivio non valido per {component_name}.")
        _safe_extract_zip(archive_path, extracted_dir)
        _apply_component_files(current_dir, extracted_dir, replace_mode=replace_mode)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def _download_file(url: str, destination: Path, timeout: int = 30) -> None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response, destination.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    except HTTPError as exc:  # pragma: no cover - network dependent
        raise UpdateError(f"Download fallito con errore HTTP {exc.code}.") from exc
    except URLError as exc:  # pragma: no cover - network dependent
        raise UpdateError(f"Download fallito: {exc.reason}") from exc


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise UpdateError("Archivio ZIP non valido.")
        zf.extractall(destination)


def _apply_component_files(current_dir: Path, extracted_dir: Path, *, replace_mode: str) -> None:
    staged_files = [path for path in extracted_dir.rglob("*") if path.is_file()]
    if not staged_files:
        raise UpdateError("Archivio aggiornamento vuoto.")

    if replace_mode == "dir":
        staged_internal = extracted_dir / "_internal"
        if not staged_internal.exists():
            raise UpdateError("Archivio runtime non valido: cartella _internal mancante.")
        target_dir = current_dir / "_internal"
        backup_dir = current_dir / "_internal.previous"
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        if target_dir.exists():
            os.replace(target_dir, backup_dir)
        os.replace(staged_internal, target_dir)
        shutil.rmtree(backup_dir, ignore_errors=True)
        return

    if replace_mode == "file":
        staged_exe = extracted_dir / APP_EXE_NAME
        if not staged_exe.exists():
            raise UpdateError(f"Archivio app non valido: file {APP_EXE_NAME} mancante.")
        target_exe = current_dir / APP_EXE_NAME
        temp_target = current_dir / f"{APP_EXE_NAME}.new"
        shutil.copy2(staged_exe, temp_target)
        os.replace(temp_target, target_exe)
        return

    raise UpdateError(f"replace_mode non supportato: {replace_mode}")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
