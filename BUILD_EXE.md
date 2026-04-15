# Build a standalone Windows EXE (PyInstaller)

This project is a PyQt6 desktop app. The simplest way to distribute it on Windows is to build a standalone `.exe` using PyInstaller.

## One-command build

From the repo root:

- Double-click `build_exe.bat`, or
- Run in PowerShell:

```powershell
.\build_exe.bat
```

The output will be:

- `dist/PDFSplitCombine.exe`

## Notes

- Build on the same OS/architecture you plan to distribute to (Windows x64 → Windows x64).
- If PyQt6 fails to install, you are likely using a non-standard Python build on Windows (e.g., MinGW). Install official CPython from python.org and rebuild.
