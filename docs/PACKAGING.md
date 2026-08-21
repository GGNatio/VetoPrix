# Guide : créer un .exe Windows + installateur

Tu es sur **macOS**. Un `.exe` Windows se compile idéalement **sur une machine Windows** (ou une VM). Ce guide est étape par étape pour Windows 10/11.

---

## Partie A — Créer le `.exe` avec PyInstaller

### 1. Préparer Windows

1. Installe [Python 3.11+](https://www.python.org/downloads/windows/)  
   Coche **« Add python.exe to PATH »**.
2. Ouvre **PowerShell**.
3. Clone le projet :

```powershell
git clone https://github.com/GGNatio/VetoPrix.git
cd VetoPrix
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

Remplace `OWNER` par ton pseudo GitHub.

### 2. Tester l’app en Python

```powershell
python main.py
```

Si ça s’ouvre, continue.

### 3. Générer le .exe

```powershell
pyinstaller --noconfirm --windowed --name VetoPrix `
  --add-data "VERSION;." `
  --add-data "update_helper.py;." `
  main.py
```

Sous Windows, le séparateur `--add-data` est `;` (pas `:`).

Résultat :

- `dist\VetoPrix\VetoPrix.exe` — lanceur
- plein de DLL à côté (dossier entier à distribuer, pas seulement le .exe)

### 4. Tester

Double-clique `dist\VetoPrix\VetoPrix.exe`.

> **Note MAJ** : le système de mise à jour actuel télécharge le **code source** (zipball GitHub). Pour une app packagée en .exe, une évolution ultérieure consistera à joindre un asset `VetoPrix-windows.zip` à chaque Release et à faire télécharger cet asset plutôt que le zipball. Le bouton MAJ reste utilisable en mode « code source Python ».

---

## Partie B — Installateur (Inno Setup)

### 1. Installer Inno Setup

Télécharge : https://jrsoftware.org/isinfo.php  
Installe la version standard.

### 2. Script d’installateur

Un modèle est fourni dans `installer/vetoprix.iss`. Ouvre-le avec Inno Setup Compiler.

Vérifie / adapte :

- `MyAppVersion` → même numéro que `VERSION`
- `Source` → chemin vers `dist\VetoPrix\*`

### 3. Compiler l’installateur

1. Ouvre `installer/vetoprix.iss` dans Inno Setup
2. **Build → Compile**
3. L’installateur sort dans `installer/output/VetoPrixSetup.exe`

### 4. Distribuer

- Envoie `VetoPrixSetup.exe` aux utilisateurs
- Ou joins-le à une **GitHub Release** comme fichier joint

---

## Partie C — Workflow de release recommandé

À chaque nouvelle version :

1. Bump `VERSION` (ex. `0.2.0`)
2. Commit + push
3. Sur Windows : rebuild PyInstaller + Inno Setup
4. Sur GitHub → **Releases → Draft a new release**
   - Tag : `v0.2.0`
   - Joindre `VetoPrixSetup.exe` (optionnel mais idéal)
5. Les utilisateurs en mode Python cliquent **MAJ** dans l’app

---

## Alternatives rapides

| Outil | Usage |
|-------|--------|
| **PyInstaller** | .exe + dépendances |
| **Inno Setup** | Installateur classique Windows |
| **Briefcase / cx_Freeze** | Alternatives à PyInstaller |
| **GitHub Actions** | Build Windows automatique dans le cloud (avancé) |

Si tu veux, on pourra ensuite automatiser le build Windows via GitHub Actions pour ne plus avoir besoin d’une VM locale.
