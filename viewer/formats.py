"""
viewer/formats.py
Supported image format registry for HEIC Photo Viewer.
"""

from __future__ import annotations

# All lowercase extensions (include the dot)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".heic", ".heif",           # Primary HEIC/HEIF formats
    ".jpg", ".jpeg",             # JPEG
    ".png",                      # PNG
    ".webp",                     # WebP
    ".bmp",                      # Bitmap
    ".tiff", ".tif",             # TIFF
    ".gif",                      # GIF (first frame)
    ".avif",                     # AVIF (via pillow_heif)
    ".ico",                      # Windows icon
})

# Human-readable file dialog filter string
FILE_DIALOG_FILTER = (
    "All Supported Images",
    " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS)),
)

# Per-format groups for the dialog (optional secondary filters)
FILE_DIALOG_GROUPS: list[tuple[str, str]] = [
    ("HEIC / HEIF", "*.heic *.heif"),
    ("JPEG", "*.jpg *.jpeg"),
    ("PNG", "*.png"),
    ("WebP", "*.webp"),
    ("TIFF", "*.tiff *.tif"),
    ("GIF", "*.gif"),
    ("AVIF", "*.avif"),
    ("BMP / ICO", "*.bmp *.ico"),
]


def is_supported(path: str) -> bool:
    """Return True if *path* has a supported image extension."""
    import os
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTENSIONS


def get_supported_files(folder: str, recursive: bool = False) -> list[str]:
    """
    Return sorted list of supported image paths within *folder*.
    If *recursive* is True, walks all subdirectories.
    """
    import os

    results: list[str] = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                    results.append(os.path.join(root, name))
    else:
        try:
            entries = os.listdir(folder)
        except OSError:
            return []
        for name in entries:
            if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                results.append(os.path.join(folder, name))

    results.sort(key=lambda p: os.path.basename(p).lower())
    return results
