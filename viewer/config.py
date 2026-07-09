"""
viewer/config.py
Settings persistence for HEIC Photo Viewer.
All settings are stored as a JSON file in %APPDATA%\\HEICViewer\\settings.json.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _get_settings_path() -> str:
    """Return the path to the settings JSON file."""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    folder = os.path.join(appdata, "HEICViewer")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    # Appearance
    theme: Literal["dark", "light"] = "dark"
    background_color: str = "#1b1b22"

    # Startup
    startup_folder: str = ""
    remember_window_state: bool = True

    # Window state (persisted)
    window_geometry: str = "1200x800"
    window_maximized: bool = False

    # Cache
    cache_size_mb: int = 400          # Max RAM used by image cache
    thumbnail_size: int = 80          # px, square

    # Slideshow
    slideshow_interval_s: float = 3.0

    # Zoom
    zoom_with_ctrl: bool = False       # If True, require Ctrl+Wheel for zoom
    zoom_smooth_factor: float = 1.2    # Multiplier per scroll step

    # Recent files/folders (most-recent-first)
    recent_files: list[str] = field(default_factory=list)
    recent_folders: list[str] = field(default_factory=list)
    max_recent: int = 20

    # Export
    export_quality: int = 95

    # Misc
    confirm_delete: bool = True
    delete_to_recycle_bin: bool = True  # False = permanent delete


# ---------------------------------------------------------------------------
# Load / save helpers
# ---------------------------------------------------------------------------

def load_settings() -> Settings:
    """Load settings from disk. Returns defaults on any error."""
    path = _get_settings_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Merge: start from defaults, then apply saved values
        defaults = asdict(Settings())
        defaults.update({k: v for k, v in data.items() if k in defaults})
        return Settings(**defaults)
    except FileNotFoundError:
        return Settings()
    except Exception as exc:
        logger.warning("Could not load settings (%s); using defaults.", exc)
        return Settings()


def save_settings(settings: Settings) -> None:
    """Persist settings to disk."""
    path = _get_settings_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(settings), fh, indent=2)
    except Exception as exc:
        logger.warning("Could not save settings: %s", exc)


def add_recent_file(settings: Settings, path: str) -> None:
    """Add a file to the recent-files list (deduplicates, trims to max_recent)."""
    lst = [p for p in settings.recent_files if p != path]
    lst.insert(0, path)
    settings.recent_files = lst[: settings.max_recent]


def add_recent_folder(settings: Settings, path: str) -> None:
    """Add a folder to the recent-folders list."""
    lst = [p for p in settings.recent_folders if p != path]
    lst.insert(0, path)
    settings.recent_folders = lst[: settings.max_recent]
