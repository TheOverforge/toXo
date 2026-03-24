@echo off
echo === toXo Build Script ===
echo.

:: Install PyInstaller if not present
pip show pyinstaller >nul 2>&1 || pip install pyinstaller

echo Building with PyInstaller...
pyinstaller ^
    --windowed ^
    --onedir ^
    --name toXo ^
    --icon "shared\assets\images\app_icon.ico" ^
    --add-data "shared\assets\images;shared\assets\images" ^
    --add-data "shared\assets\icons;shared\assets\icons" ^
    --add-data "shared\assets\sounds;shared\assets\sounds" ^
    --hidden-import PyQt6.sip ^
    --hidden-import PyQt6.QtNetwork ^
    --hidden-import pyqtgraph ^
    main.py

echo.
echo Done. Output: dist\toXo\
echo Now compile installer.iss with Inno Setup.
pause
