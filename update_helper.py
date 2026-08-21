#!/usr/bin/env python3
"""
Helper de mise à jour VetoPrix — lancé en processus séparé.

1. Attend que le processus principal (pid) se termine
2. Extrait le zip téléchargé
3. Copie les fichiers dans le dossier d'installation (sans toucher data/)
4. Relance l'application
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_for_exit(pid: int, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pid):
            # Petite pause pour laisser les handles fichiers se libérer (Windows)
            time.sleep(0.8)
            return
        time.sleep(0.3)
    # Continue quand même : mieux vaut tenter la MAJ


def find_extracted_root(extract_dir: Path) -> Path:
    """Le zipball GitHub contient un dossier racine unique owner-repo-sha/."""
    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    # Fallback : chercher main.py
    for p in extract_dir.rglob("main.py"):
        return p.parent
    raise FileNotFoundError("Impossible de trouver la racine du zip extrait.")


def copy_update(src_root: Path, install_dir: Path, preserve: list[str]) -> None:
    preserve_set = set(preserve)
    for item in src_root.iterdir():
        name = item.name
        if name in preserve_set:
            continue
        dest = install_dir / name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def main() -> int:
    parser = argparse.ArgumentParser(description="VetoPrix update helper")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--preserve", nargs="*", default=["data", ".git", ".venv", "venv"])
    parser.add_argument("--restart", nargs="+", required=True,
                        help="Commande de relance, ex: python main.py")
    args = parser.parse_args()

    log_path = args.install_dir / ".update_tmp" / "update.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    try:
        log(f"Attente fin PID {args.pid}…")
        wait_for_exit(args.pid)

        extract_dir = args.install_dir / ".update_tmp" / "extract"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)

        log(f"Extraction {args.zip}")
        with zipfile.ZipFile(args.zip, "r") as zf:
            zf.extractall(extract_dir)

        src_root = find_extracted_root(extract_dir)
        log(f"Source : {src_root}")
        log(f"Cible  : {args.install_dir}")
        log(f"Préservés : {args.preserve}")

        copy_update(src_root, args.install_dir, list(args.preserve))
        log("Fichiers mis à jour.")

        # Nettoyage zip (garder le log)
        try:
            args.zip.unlink(missing_ok=True)
        except TypeError:
            if args.zip.exists():
                args.zip.unlink()
        shutil.rmtree(extract_dir, ignore_errors=True)

        log(f"Relance : {' '.join(args.restart)}")
        kwargs = {"cwd": str(args.install_dir)}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x00000200 | 0x00000008  # new group + detached
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(args.restart, **kwargs)
        log("OK")
        return 0
    except Exception as e:
        log(f"ERREUR : {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
