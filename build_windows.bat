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

echo [INFO] Compilo eseguibile...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PlannerTurni app.py
if errorlevel 1 goto :error

if exist "planner_data.json" (
  copy /Y "planner_data.json" "dist\planner_data.json" >nul
)

echo.
echo [OK] Build completata:
echo      dist\PlannerTurni.exe
echo      dist\planner_data.json
exit /b 0

:error
echo.
echo [ERRORE] Build non completata.
exit /b 1
