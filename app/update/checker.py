"""
Vérification et application des mises à jour via GitHub Releases.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.config import (
    APP_ROOT,
    ASSET_MACOS_ZIP,
    ASSET_WINDOWS_ZIP,
    GITHUB_API,
    GITHUB_REPO,
    GITHUB_TOKEN,
    UPDATE_PRESERVE,
    UPDATE_TIMEOUT,
    get_install_dir,
    get_local_version,
    is_frozen,
)


@dataclass
class ReleaseAsset:
    name: str
    browser_download_url: str
    size: int = 0


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str
    body: str
    zipball_url: str
    html_url: str
    assets: list[ReleaseAsset] = field(default_factory=list)


def _parse_version(text: str) -> tuple:
    text = text.strip().lstrip("vV")
    parts = re.split(r"[^\d]+", text)
    nums = []
    for p in parts:
        if p.isdigit():
            nums.append(int(p))
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def version_is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def _resolve_token() -> str:
    token = (GITHUB_TOKEN or os.environ.get("VETOPRIX_GITHUB_TOKEN") or "").strip()
    if token:
        return token
    try:
        proc = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return ""


def _auth_headers(download: bool = False) -> dict:
    headers = {
        "User-Agent": f"VetoPrix/{get_local_version()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if download:
        headers["Accept"] = "application/octet-stream"
    else:
        headers["Accept"] = "application/vnd.github+json"
    token = _resolve_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_auth_headers(False))
    with urllib.request.urlopen(req, timeout=UPDATE_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_release(repo: Optional[str] = None) -> Optional[ReleaseInfo]:
    repo = repo or GITHUB_REPO
    if not repo or "OWNER" in repo or "/" not in repo:
        raise ValueError(
            "Dépôt GitHub non configuré. Modifiez GITHUB_REPO dans app/config.py."
        )
    url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    try:
        data = _http_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(
                "Release introuvable (404). Si le dépôt est privé, "
                "passe-le en public ou définis VETOPRIX_GITHUB_TOKEN."
            ) from e
        raise
    tag = data.get("tag_name") or ""
    version = tag.lstrip("vV")
    assets = [
        ReleaseAsset(
            name=a.get("name") or "",
            browser_download_url=a.get("browser_download_url") or "",
            size=int(a.get("size") or 0),
        )
        for a in (data.get("assets") or [])
        if a.get("browser_download_url")
    ]
    return ReleaseInfo(
        tag=tag,
        version=version,
        name=data.get("name") or tag,
        body=data.get("body") or "",
        zipball_url=data.get("zipball_url") or "",
        html_url=data.get("html_url") or "",
        assets=assets,
    )


def pick_download_url(release: ReleaseInfo) -> tuple[str, str]:
    """
    Choisit l'URL de téléchargement selon la plateforme.
    Retourne (url, label).
    """
    by_name = {a.name: a for a in release.assets}

    if is_frozen() and sys.platform == "win32":
        asset = by_name.get(ASSET_WINDOWS_ZIP)
        if asset:
            return asset.browser_download_url, ASSET_WINDOWS_ZIP
        raise FileNotFoundError(
            f"Asset {ASSET_WINDOWS_ZIP} absent de la release {release.tag}. "
            "Attendez la fin du build GitHub Actions ou joignez le zip à la release."
        )

    if is_frozen() and sys.platform == "darwin":
        asset = by_name.get(ASSET_MACOS_ZIP)
        if asset:
            return asset.browser_download_url, ASSET_MACOS_ZIP
        # Repli : zipball source (dev)
        if release.zipball_url:
            return release.zipball_url, "source-zipball"
        raise FileNotFoundError(f"Asset {ASSET_MACOS_ZIP} absent de la release.")

    # Mode source Python
    if release.zipball_url:
        return release.zipball_url, "source-zipball"
    raise FileNotFoundError("Aucun fichier de mise à jour disponible sur la release.")


def check_for_update(repo: Optional[str] = None) -> dict:
    local = get_local_version()
    try:
        release = fetch_latest_release(repo)
    except Exception as e:
        return {
            "available": False,
            "local": local,
            "remote": None,
            "release": None,
            "error": str(e),
        }
    if release is None:
        return {
            "available": False,
            "local": local,
            "remote": None,
            "release": None,
            "error": "Aucune release trouvée sur GitHub.",
        }
    available = version_is_newer(release.version, local)
    return {
        "available": available,
        "local": local,
        "remote": release.version,
        "release": release,
        "error": None,
    }


def download_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # browser_download_url n'a pas besoin de Accept octet-stream
    headers = _auth_headers(False)
    headers["Accept"] = "application/octet-stream"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    return dest


def start_update_and_quit(release: ReleaseInfo) -> None:
    """
    Télécharge le bon asset (Windows zip embarqué ou sources),
    lance le helper de MAJ, quitte l'app. data/ est préservée.
    """
    tmp_dir = APP_ROOT / ".update_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    url, label = pick_download_url(release)
    zip_path = tmp_dir / f"vetoprix_{release.version}_{label.replace('/', '_')}.zip"
    download_file(url, zip_path)

    install_dir = get_install_dir()

    if is_frozen():
        restart_cmd = [sys.executable]
        args = [
            sys.executable,
            "--update-helper",
            "--pid", str(os.getpid()),
            "--zip", str(zip_path),
            "--install-dir", str(install_dir),
            "--preserve", *UPDATE_PRESERVE,
            "--restart", *restart_cmd,
        ]
    else:
        helper = APP_ROOT / "update_helper.py"
        if not helper.exists():
            helper = Path(__file__).resolve().parents[2] / "update_helper.py"
        if not helper.exists():
            raise FileNotFoundError(f"Helper de mise à jour introuvable : {helper}")
        restart_cmd = [sys.executable, str(APP_ROOT / "main.py")]
        args = [
            sys.executable,
            str(helper),
            "--pid", str(os.getpid()),
            "--zip", str(zip_path),
            "--install-dir", str(install_dir),
            "--preserve", *UPDATE_PRESERVE,
            "--restart", *restart_cmd,
        ]

    kwargs = {
        "cwd": str(install_dir),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "start_new_session": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000200 | 0x00000008
        kwargs.pop("start_new_session", None)

    subprocess.Popen(args, **kwargs)

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.quit()
    else:
        sys.exit(0)
