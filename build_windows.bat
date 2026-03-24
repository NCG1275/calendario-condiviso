@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creo ambiente virtuale...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"

echo [INFO] Aggiorno pip...
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [INFO] Installo dipendenze build...
python -m pip install pyinstaller PySide6
if errorlevel 1 goto :error

echo [INFO] Compilo release modulare...
python build_release.py
if errorlevel 1 goto :error

echo.
echo [OK] Build completata:
echo      release\PlannerTurniInstaller.exe
echo      release\PlannerTurniLauncher.exe
echo      release\planner-release-manifest.json
echo      release\planner-app-win64.zip
echo      release\planner-runtime-win64.zip
echo      release\planner-portable-win64.zip
exit /b 0

:error
echo.
echo [ERRORE] Build non completata.
exit /b 1
