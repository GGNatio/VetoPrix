"""
Configuration centralisée de VetoPrix.
Modifier ici pour changer version, dépôt GitHub, chemins, etc.
"""
import sys
from pathlib import Path


def _detect_app_root() -> Path:
    """Dossier données utilisateur (DB, tarifs importés, cache MAJ)."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        # Bundle macOS .app → Application Support (writable)
        if sys.platform == "darwin" and ".app/Contents/MacOS" in str(exe):
            root = Path.home() / "Library" / "Application Support" / "VetoPrix"
            root.mkdir(parents=True, exist_ok=True)
            return root
        # Windows / Mac onedir portable → à côté du binaire
        return exe.parent
    return Path(__file__).resolve().parent.parent


def _resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_install_dir() -> Path:
    """
    Dossier à remplacer lors d'une MAJ binaire.
    Windows frozen = dossier du .exe ; source = racine projet.
    """
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if sys.platform == "darwin" and ".app/Contents/MacOS" in str(exe):
            return exe.parents[2]  # Xxx.app
        return exe.parent
    return Path(__file__).resolve().parent.parent


APP_ROOT = _detect_app_root()
RESOURCE_DIR = _resource_dir()


def _version_file() -> Path:
    local = APP_ROOT / "VERSION"
    if local.exists():
        return local
    bundled = RESOURCE_DIR / "VERSION"
    if bundled.exists():
        return bundled
    return local


VERSION_FILE = _version_file()

GITHUB_REPO = "GGNatio/VetoPrix"
GITHUB_TOKEN = ""
GITHUB_API = "https://api.github.com"

# Noms d'assets attendus sur les GitHub Releases
ASSET_WINDOWS_ZIP = "VetoPrix-windows.zip"
ASSET_MACOS_ZIP = "VetoPrix-macos.zip"

UPDATE_PRESERVE = (
    "data",
    ".git",
    ".venv",
    "venv",
    ".update_tmp",
)

UPDATE_TIMEOUT = 20

# Dossier des tarifs CSV livrés avec l'app / les releases
TARIFS_DIRNAME = "tarifs"


def get_local_version() -> str:
    try:
        return _version_file().read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def tarifs_dirs() -> list[Path]:
    """Emplacements possibles des CSV de tarifs (install + bundle)."""
    dirs = []
    for base in (APP_ROOT, get_install_dir(), RESOURCE_DIR):
        p = base / TARIFS_DIRNAME
        if p not in dirs:
            dirs.append(p)
    return dirs
