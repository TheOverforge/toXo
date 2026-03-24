"""Centralised project paths — import from here instead of Path(__file__).parent.parent."""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller: sys._MEIPASS is the folder where the exe unpacks everything
    PROJECT_ROOT: Path = Path(sys._MEIPASS)
else:
    # Normal: shared/config/paths.py → shared/config/ → shared/ → project root
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

ASSETS_DIR: Path = PROJECT_ROOT / "shared" / "assets"
ICONS_DIR: Path = ASSETS_DIR / "icons"
IMAGES_DIR: Path = ASSETS_DIR / "images"
SOUNDS_DIR: Path = ASSETS_DIR / "sounds"
