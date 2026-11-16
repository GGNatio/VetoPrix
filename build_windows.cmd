@echo off
REM Construit VetoPrix.exe avec Python embarque (Windows)
setlocal
cd /d "%~dp0"

echo ==^> Installation des dependances de build...
python -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 (
    python3 -m pip install -q -r requirements.txt pyinstaller
)

echo ==^> Build PyInstaller...
python -m PyInstaller --noconfirm vetoprix.spec
if errorlevel 1 python3 -m PyInstaller --noconfirm vetoprix.spec

echo.
echo OK — application generee :
echo   dist\VetoPrix\VetoPrix.exe
echo.
echo Double-clique sur dist\VetoPrix\VetoPrix.exe  (Python n'est plus requis).
echo Distribue tout le dossier dist\VetoPrix\ (pas seulement le .exe).
pause
endlocal
