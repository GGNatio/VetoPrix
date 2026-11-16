@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM 1) Binaire embarque (Python inclus)
if exist "%~dp0dist\VetoPrix\VetoPrix.exe" (
    echo [VetoPrix] Lancement version embarquee...
    start "" "%~dp0dist\VetoPrix\VetoPrix.exe"
    exit /b 0
)
if exist "%~dp0VetoPrix\VetoPrix.exe" (
    echo [VetoPrix] Lancement version embarquee...
    start "" "%~dp0VetoPrix\VetoPrix.exe"
    exit /b 0
)
if exist "%~dp0VetoPrix.exe" (
    echo [VetoPrix] Lancement version embarquee...
    start "" "%~dp0VetoPrix.exe"
    exit /b 0
)

REM 2) Python systeme
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where python3 >nul 2>&1 && set "PY=python3"

if not defined PY (
    echo [VetoPrix] Ni version embarquee ni Python introuvable.
    echo.
    echo Options :
    echo   1. Lance build_windows.cmd  (une fois, avec Python installe)
    echo      puis reutilise ce lanceur — Python ne sera plus necessaire.
    echo   2. Ou installe Python : https://www.python.org/downloads/
    echo      (coche "Add python.exe to PATH")
    pause
    exit /b 1
)

echo [VetoPrix] Lancement avec %PY% ...
"%PY%" main.py
if errorlevel 1 (
    echo.
    echo [VetoPrix] L'application s'est terminee avec une erreur.
    pause
)
endlocal
