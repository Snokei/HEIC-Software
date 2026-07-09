"""
viewer/image_loader.py
Thread-safe image loading with ICC profile conversion and EXIF orientation correction.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageCms

from .exif_reader import ExifData, read_exif

logger = logging.getLogger(__name__)

# Shared sRGB profile (created once)
_SRGB_PROFILE: Optional[ImageCms.ImageCmsProfile] = None


def _get_srgb_profile() -> ImageCms.ImageCmsProfile:
    global _SRGB_PROFILE
    if _SRGB_PROFILE is None:
        _SRGB_PROFILE = ImageCms.createProfile("sRGB")
    return _SRGB_PROFILE


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class LoadResult:
    image: Optional[Image.Image]
    exif: Optional[ExifData]
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.image is not None and not self.error


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------

def load_image(path: str) -> LoadResult:
    """
    Open an image from *path*, apply ICC profile conversion to sRGB,
    and auto-rotate according to EXIF orientation.

    Returns a LoadResult. Never raises — errors are captured in result.error.
    """
    try:
        img = Image.open(path)

        # Force full decode (important for HEIC and TIFF)
        img.load()

        # --- Read EXIF BEFORE ICC conversion ---
        # ImageCms.profileToProfile() creates a new Image that does NOT copy
        # the .info dict, so EXIF bytes are lost after conversion.
        try:
            exif = read_exif(img)
        except Exception as exc:
            logger.debug("EXIF read failed for %s: %s", path, exc)
            exif = ExifData()

        # --- ICC profile → sRGB conversion ---
        icc_bytes = img.info.get("icc_profile")
        if icc_bytes:
            try:
                input_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
                srgb = _get_srgb_profile()
                # Only convert modes that CMS handles well
                if img.mode in ("RGB", "RGBA", "L", "CMYK"):
                    img = ImageCms.profileToProfile(img, input_profile, srgb)
            except Exception as exc:
                logger.debug("ICC conversion skipped for %s: %s", path, exc)

        # --- Ensure we have a usable mode ---
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")

        # --- EXIF orientation correction ---
        if exif.needs_rotation:
            try:
                img = img.rotate(exif.rotation_degrees, expand=True)
            except Exception as exc:
                logger.debug("Orientation rotate failed: %s", exc)

        return LoadResult(image=img, exif=exif)

    except FileNotFoundError:
        return LoadResult(image=None, exif=None, error=f"File not found: {path}")
    except PermissionError:
        return LoadResult(image=None, exif=None, error=f"Permission denied: {path}")
    except Exception as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return LoadResult(image=None, exif=None, error=str(exc))
