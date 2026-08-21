"""
Configuration centralisée de VetoPrix.
Modifier ici pour changer version, dépôt GitHub, chemins, etc.
"""
from pathlib import Path

# Racine du projet (dossier contenant main.py)
APP_ROOT = Path(__file__).resolve().parent.parent

# Version locale (fichier VERSION à la racine)
VERSION_FILE = APP_ROOT / "VERSION"

# Dépôt GitHub utilisé pour les mises à jour (owner/repo)
# Sera renseigné automatiquement après création du repo, ou à la main.
GITHUB_REPO = "GGNatio/VetoPrix"


# API GitHub (releases)
GITHUB_API = "https://api.github.com"

# Fichiers / dossiers à ne JAMAIS écraser lors d'une mise à jour
UPDATE_PRESERVE = (
    "data",           # base SQLite + imports utilisateur
    ".git",
    ".venv",
    "venv",
    ".update_tmp",
)

# Timeout réseau (secondes)
UPDATE_TIMEOUT = 20


def get_local_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"
