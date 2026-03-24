param(
    [string]$PythonCmd = "py"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing/updating build dependencies..."
& $PythonCmd -m pip install --upgrade pip
& $PythonCmd -m pip install --upgrade pyinstaller PySide6

Write-Host "Building modular release..."
& $PythonCmd build_release.py

Write-Host ""
Write-Host "Done. Release assets created in: release\\"
Write-Host "Installer: release\\PlannerTurniInstaller.exe"
