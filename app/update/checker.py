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
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import (
    APP_ROOT,
    GITHUB_API,
    GITHUB_REPO,
    GITHUB_TOKEN,
    UPDATE_PRESERVE,
    UPDATE_TIMEOUT,
    get_local_version,
)


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str
    body: str
    zipball_url: str
    html_url: str


def _parse_version(text: str) -> tuple:
    """'v1.2.3' ou '1.2.3' → (1, 2, 3). Segments non numériques → 0."""
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


def _auth_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"VetoPrix/{get_local_version()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (GITHUB_TOKEN or os.environ.get("VETOPRIX_GITHUB_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_auth_headers())
    with urllib.request.urlopen(req, timeout=UPDATE_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_release(repo: Optional[str] = None) -> Optional[ReleaseInfo]:
    """
    Récupère la dernière release GitHub.
    Retourne None si aucune release / repo mal configuré.
    """
    repo = repo or GITHUB_REPO
    if not repo or "OWNER" in repo or "/" not in repo:
        raise ValueError(
            "Dépôt GitHub non configuré. Modifiez GITHUB_REPO dans app/config.py "
            "(ex: 'ton-user/VetoPrix')."
        )
    url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    try:
        data = _http_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    tag = data.get("tag_name") or ""
    version = tag.lstrip("vV")
    return ReleaseInfo(
        tag=tag,
        version=version,
        name=data.get("name") or tag,
        body=data.get("body") or "",
        zipball_url=data.get("zipball_url") or "",
        html_url=data.get("html_url") or "",
    )


def check_for_update(repo: Optional[str] = None) -> dict:
    """
    Compare la version locale à la dernière release.
    Retourne un dict : available, local, remote, release (ReleaseInfo|None), error
    """
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


def download_zip(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=_auth_headers())
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)
    return dest


def start_update_and_quit(release: ReleaseInfo) -> None:
    """
    Télécharge le zip de la release, lance update_helper.py, quitte l'app.
    La base data/ est préservée par le helper.
    """
    tmp_dir = APP_ROOT / ".update_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    zip_path = tmp_dir / f"vetoprix_{release.version}.zip"
    download_zip(release.zipball_url, zip_path)

    helper = APP_ROOT / "update_helper.py"
    if not helper.exists():
        raise FileNotFoundError(f"Helper de mise à jour introuvable : {helper}")

    # Relance : même interpréteur + main.py
    restart_cmd = [sys.executable, str(APP_ROOT / "main.py")]

    args = [
        sys.executable,
        str(helper),
        "--pid", str(os.getpid()),
        "--zip", str(zip_path),
        "--install-dir", str(APP_ROOT),
        "--preserve", *UPDATE_PRESERVE,
        "--restart", *restart_cmd,
    ]
    # Détaché pour survivre à la fermeture de l'app
    kwargs = {
        "cwd": str(APP_ROOT),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "start_new_session": True,
    }
    if sys.platform == "win32":
        # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
        kwargs["creationflags"] = 0x00000200 | 0x00000008
        kwargs.pop("start_new_session", None)

    subprocess.Popen(args, **kwargs)

    # Quitter l'app Qt proprement
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.quit()
    else:
        sys.exit(0)
