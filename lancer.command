#!/bin/bash
# Double-clic possible sur macOS (fichier .command)
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"

# 1) Bundle embarqué (Python inclus)
if [ -d "$ROOT/dist/VetoPrix.app" ]; then
  echo "[VetoPrix] Lancement version embarquée (dist/VetoPrix.app)…"
  exec open "$ROOT/dist/VetoPrix.app"
fi
if [ -d "$ROOT/VetoPrix.app" ]; then
  echo "[VetoPrix] Lancement version embarquée (VetoPrix.app)…"
  exec open "$ROOT/VetoPrix.app"
fi
if [ -x "$ROOT/dist/VetoPrix/VetoPrix" ]; then
  echo "[VetoPrix] Lancement version embarquée…"
  exec "$ROOT/dist/VetoPrix/VetoPrix"
fi

# 2) Python système
PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
fi

if [ -z "$PY" ]; then
  echo "[VetoPrix] Ni version embarquée ni Python introuvable."
  echo ""
  echo "Options :"
  echo "  1. Lance une fois :  ./build_mac.sh"
  echo "     (nécessite Python temporairement), puis double-clique"
  echo "     sur dist/VetoPrix.app — plus besoin de Python ensuite."
  echo "  2. Ou installe Python :  brew install python"
  read -r -p "Appuyez sur Entrée pour fermer..."
  exit 1
fi

echo "[VetoPrix] Lancement avec $PY ..."
exec "$PY" main.py
