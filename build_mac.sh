#!/bin/bash
# Construit VetoPrix.app avec Python embarqué (macOS)
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installation des dépendances de build…"
python3 -m pip install -q -r requirements.txt pyinstaller

echo "==> Build PyInstaller…"
python3 -m PyInstaller --noconfirm vetoprix.spec

echo ""
echo "OK — application générée :"
echo "  dist/VetoPrix.app"
echo ""
echo "Double-clique sur dist/VetoPrix.app  (Python n'est plus requis)."
echo "Ou lance :  open dist/VetoPrix.app"
