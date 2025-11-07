Photo2STL - Package
====================

This package contains:
- windows_photogrammetry_stl_tool.py  (single-file PySide6 app)
- build_windows_exe.ps1               (PowerShell script to build with PyInstaller on Windows)
- .github/workflows/build-windows-exe.yml  (GitHub Actions workflow to build a Windows exe automatically)
- README (this file)

Options to get a Windows executable:

1) Build locally on your Windows PC (recommended)
   - Install Python 3.10+ and Git.
   - Clone/copy these files to a folder on your Windows machine.
   - Open PowerShell in that folder and run:
       .\\build_windows_exe.ps1
   - The script will install required packages and run PyInstaller to produce Photo2STL.exe in the 'dist' folder.

2) Build in GitHub Actions (CI)
   - Create a new GitHub repo, push all files to the 'main' branch.
   - The workflow in .github/workflows/build-windows-exe.yml will run and create the Photo2STL.exe artifact.
   - Download the artifact from the Actions run page.

Important notes:
- COLMAP and OpenMVS are external native programs and are NOT bundled. You must install them on Windows separately and either add them to PATH or configure their paths in the app settings.
- Single-photo reconstructions are limited; for single-image workflow consider using AI API pipeline (add your API integration).
- Test with sample photos and check output folder (default: photo2stl_output).

If you want, I can also:
- Push this repo to a new GitHub repo for you and trigger the Actions build (I can prepare the repo content here).
- Or I can prepare a binary for you if you provide a Windows build environment or allow me to use GitHub Actions (I can provide steps to do it yourself).

