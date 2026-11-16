"""
Import automatique des CSV présents dans tarifs/.
Les fichiers déjà importés (même nom + même taille) sont ignorés.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import APP_ROOT, tarifs_dirs
from app.data.csv_importer import import_csv
from app.data.molecule_mapper import sync_molecules_from_anmv


def _state_path() -> Path:
    path = APP_ROOT / "data" / "imported_tarifs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_state() -> dict:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _file_key(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path.name}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        return path.name


def discover_tarif_csvs() -> list[Path]:
    found = []
    seen = set()
    for d in tarifs_dirs():
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.csv")):
            key = str(p.resolve()) if p.exists() else str(p)
            if key in seen:
                continue
            seen.add(key)
            found.append(p)
    return found


def auto_import_tarifs() -> dict:
    """
    Importe les nouveaux CSV du dossier tarifs/.
    Retourne {imported: [...], skipped: [...], errors: [...]}
    """
    state = _load_state()
    imported, skipped, errors = [], [], []

    for csv_path in discover_tarif_csvs():
        key = _file_key(csv_path)
        prev = state.get(csv_path.name)
        if prev == key:
            skipped.append(csv_path.name)
            continue
        try:
            result = import_csv(str(csv_path))
            state[csv_path.name] = key
            imported.append({
                "file": csv_path.name,
                "date_import": result.get("date_import"),
                "nb_produits": result.get("nb_produits"),
            })
        except Exception as e:
            errors.append({"file": csv_path.name, "error": str(e)})

    if imported:
        try:
            sync_molecules_from_anmv()
        except Exception:
            pass
        _save_state(state)
    elif not errors:
        _save_state(state)

    return {"imported": imported, "skipped": skipped, "errors": errors}
