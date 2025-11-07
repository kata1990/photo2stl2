# build_windows_exe.ps1
# Usage: Run this in an elevated PowerShell on Windows where Python 3.10+ is installed.
# It will create a single-file executable using PyInstaller.
param(
    [string]$Script = "windows_photogrammetry_stl_tool.py",
    [string]$OutputDir = "dist",
    [switch]$OneFile = $true
)

python -m pip install --upgrade pip
python -m pip install PySide6 trimesh numpy plyfile pyinstaller

$pyinstallerArgs = @("--noconfirm", "--clean")
if ($OneFile) { $pyinstallerArgs += "--onefile" }
$pyinstallerArgs += "--add-data","\"%CD%\\photo2stl_output;photo2stl_output\""
$pyinstallerArgs += "--name","Photo2STL"
$pyinstallerArgs += $Script

pyinstaller @pyinstallerArgs

Write-Host "Build finished. Check .\\dist or the created .exe file."