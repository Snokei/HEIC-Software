"""
viewer/exif_reader.py
Full EXIF + GPS metadata parser for HEIC Photo Viewer.
Returns a typed ExifData dataclass from a PIL Image.
"""

from __future__ import annotations

import datetime
import io
import logging
import struct
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Optional

from PIL import Image, ImageCms

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EXIF tag constants
# ---------------------------------------------------------------------------
TAG_MAKE           = 271
TAG_MODEL          = 272
TAG_DATETIME       = 306
TAG_DATETIME_ORIG  = 36867
TAG_DATETIME_DIGI  = 36868
TAG_EXPOSURE_TIME  = 33434
TAG_F_NUMBER       = 33437
TAG_ISO            = 34855
TAG_FOCAL_LENGTH   = 37386
TAG_EXPOSURE_BIAS  = 37380
TAG_FLASH          = 37385
TAG_LENS_MODEL     = 42036      # ExifIFD lens model
TAG_LENS_MODEL_ALT = 37860      # Some cameras use this
TAG_GPS_INFO       = 34853
TAG_ORIENTATION    = 274
TAG_WIDTH          = 40962
TAG_HEIGHT         = 40963
TAG_COLOR_SPACE    = 40961
TAG_WHITE_BALANCE  = 41987
TAG_METERING_MODE  = 37383
TAG_SCENE_TYPE     = 41729

# GPS sub-tags
GPS_LATITUDE_REF   = 1
GPS_LATITUDE       = 2
GPS_LONGITUDE_REF  = 3
GPS_LONGITUDE      = 4
GPS_ALTITUDE_REF   = 5
GPS_ALTITUDE       = 6
GPS_TIMESTAMP      = 7
GPS_DATESTAMP      = 29

# Flash decoded values
FLASH_DESCRIPTIONS = {
    0x00: "No flash", 0x01: "Flash fired",
    0x05: "Flash fired, no strobe return",
    0x07: "Flash fired, strobe return light detected",
    0x09: "Flash fired, compulsory", 0x0D: "Flash fired, compulsory, no return",
    0x0F: "Flash fired, compulsory, return light",
    0x10: "Flash did not fire, compulsory",
    0x18: "Flash did not fire, auto", 0x19: "Flash fired, auto",
    0x1D: "Flash fired, auto, no return",
    0x1F: "Flash fired, auto, return detected",
    0x20: "No flash function", 0x41: "Flash fired, red-eye reduction",
    0x45: "Flash fired, red-eye, no return",
    0x47: "Flash fired, red-eye, return detected",
    0x49: "Flash fired, compulsory, red-eye",
    0x4F: "Flash fired, compulsory, red-eye, return",
    0x59: "Flash fired, auto, red-eye",
    0x5D: "Flash fired, auto, no return, red-eye",
    0x5F: "Flash fired, auto, return, red-eye",
}

METERING_MODES = {
    0: "Unknown", 1: "Average", 2: "Center Weighted",
    3: "Spot", 4: "Multi-Spot", 5: "Pattern", 6: "Partial",
}

WHITE_BALANCE = {0: "Auto", 1: "Manual"}


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class ExifData:
    # Camera
    make: str = ""
    model: str = ""
    lens_model: str = ""

    # Capture settings
    focal_length_mm: str = ""
    aperture: str = ""
    exposure_time: str = ""
    iso: str = ""
    exposure_bias: str = ""
    flash: str = ""
    white_balance: str = ""
    metering_mode: str = ""

    # Date/time
    datetime_taken: Optional[datetime.datetime] = None

    # GPS
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    gps_string: str = ""

    # Image properties
    color_space: str = ""
    icc_profile_name: str = ""
    orientation: int = 1

    # Derived
    bit_depth: int = 24

    # Raw orientation auto-rotate needed?
    needs_rotation: bool = False
    rotation_degrees: int = 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _rational_to_float(val: Any) -> Optional[float]:
    """Convert an EXIF rational (tuple or IFDRational) to float."""
    if val is None:
        return None
    if isinstance(val, tuple) and len(val) == 2:
        denom = val[1]
        if denom == 0:
            return None
        return val[0] / denom
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_datetime(raw: str) -> Optional[datetime.datetime]:
    """Parse EXIF date string 'YYYY:MM:DD HH:MM:SS'."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.datetime.strptime(raw.strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _dms_to_decimal(dms: Any, ref: str) -> Optional[float]:
    """Convert DMS tuple from EXIF GPS to decimal degrees."""
    if not dms or len(dms) < 3:
        return None
    try:
        degrees = _rational_to_float(dms[0]) or 0
        minutes = _rational_to_float(dms[1]) or 0
        seconds = _rational_to_float(dms[2]) or 0
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except Exception:
        return None


def _get_icc_profile_name(icc_bytes: bytes) -> str:
    """Extract the profile description from raw ICC profile bytes."""
    if not icc_bytes or len(icc_bytes) < 132:
        return ""
    try:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
        name = ImageCms.getProfileDescription(profile)
        return (name or "").strip()
    except Exception:
        return ""


def _bit_depth_from_mode(mode: str) -> int:
    """Estimate bit depth from PIL image mode."""
    mapping = {
        "1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32,
        "CMYK": 32, "YCbCr": 24, "LAB": 24, "HSV": 24,
        "I": 32, "F": 32, "LA": 16, "PA": 8,
        "RGB;16": 48, "RGBA;16": 64,
    }
    return mapping.get(mode, 24)


# EXIF orientation → (rotation in degrees, flip)
_ORIENTATION_MAP = {
    1: (0, False),
    2: (0, True),
    3: (180, False),
    4: (180, True),
    5: (90, True),
    6: (90, False),
    7: (270, True),
    8: (270, False),
}


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def read_exif(image: Image.Image) -> ExifData:
    """
    Parse all EXIF metadata from a PIL Image.
    Returns a populated ExifData instance.
    """
    data = ExifData()
    data.bit_depth = _bit_depth_from_mode(image.mode)

    # ICC profile name
    icc_bytes = image.info.get("icc_profile")
    if icc_bytes:
        data.icc_profile_name = _get_icc_profile_name(icc_bytes)

    try:
        exif = image.getexif()
    except Exception:
        return data

    if not exif:
        return data

    # --- Basic camera info ---
    data.make  = str(exif.get(TAG_MAKE, "")).strip()
    data.model = str(exif.get(TAG_MODEL, "")).strip()

    # --- Lens model ---
    for tag in (TAG_LENS_MODEL, TAG_LENS_MODEL_ALT):
        raw = exif.get(tag)
        if raw:
            data.lens_model = str(raw).strip()
            break

    # --- Date/time (prefer DateTimeOriginal) ---
    for tag in (TAG_DATETIME_ORIG, TAG_DATETIME, TAG_DATETIME_DIGI):
        raw = exif.get(tag)
        dt = _parse_datetime(str(raw) if raw else "")
        if dt:
            data.datetime_taken = dt
            break

    # --- Focal length ---
    fl = _rational_to_float(exif.get(TAG_FOCAL_LENGTH))
    if fl is not None:
        data.focal_length_mm = f"{fl:.1f} mm"

    # --- Aperture ---
    fn = _rational_to_float(exif.get(TAG_F_NUMBER))
    if fn is not None:
        data.aperture = f"f/{fn:.1f}"

    # --- Exposure time ---
    et = _rational_to_float(exif.get(TAG_EXPOSURE_TIME))
    if et is not None:
        if et < 1:
            try:
                frac = Fraction(et).limit_denominator(10000)
                data.exposure_time = f"1/{frac.denominator} s"
            except Exception:
                data.exposure_time = f"{et:.5f} s"
        else:
            data.exposure_time = f"{et:.1f} s"

    # --- ISO ---
    iso = exif.get(TAG_ISO)
    if iso is not None:
        data.iso = f"ISO {iso}"

    # --- Exposure bias ---
    eb = _rational_to_float(exif.get(TAG_EXPOSURE_BIAS))
    if eb is not None:
        data.exposure_bias = f"{eb:+.1f} EV"

    # --- Flash ---
    flash_code = exif.get(TAG_FLASH)
    if flash_code is not None:
        data.flash = FLASH_DESCRIPTIONS.get(int(flash_code), f"Code {flash_code}")

    # --- White balance ---
    wb = exif.get(TAG_WHITE_BALANCE)
    if wb is not None:
        data.white_balance = WHITE_BALANCE.get(int(wb), str(wb))

    # --- Metering mode ---
    mm = exif.get(TAG_METERING_MODE)
    if mm is not None:
        data.metering_mode = METERING_MODES.get(int(mm), str(mm))

    # --- Color space ---
    cs = exif.get(TAG_COLOR_SPACE)
    if cs is not None:
        data.color_space = "sRGB" if cs == 1 else ("Uncalibrated" if cs == 0xFFFF else str(cs))

    # --- Orientation ---
    orientation = exif.get(TAG_ORIENTATION, 1)
    try:
        orientation = int(orientation)
    except (TypeError, ValueError):
        orientation = 1
    data.orientation = orientation
    rot_degrees, _ = _ORIENTATION_MAP.get(orientation, (0, False))
    if rot_degrees != 0:
        data.needs_rotation = True
        data.rotation_degrees = rot_degrees

    # --- GPS ---
    try:
        gps_ifd = exif.get_ifd(TAG_GPS_INFO)
        if gps_ifd:
            lat = _dms_to_decimal(
                gps_ifd.get(GPS_LATITUDE),
                str(gps_ifd.get(GPS_LATITUDE_REF, "N"))
            )
            lon = _dms_to_decimal(
                gps_ifd.get(GPS_LONGITUDE),
                str(gps_ifd.get(GPS_LONGITUDE_REF, "E"))
            )
            if lat is not None and lon is not None:
                data.latitude = lat
                data.longitude = lon
                data.gps_string = f"{abs(lat):.6f}° {'N' if lat >= 0 else 'S'},  {abs(lon):.6f}° {'E' if lon >= 0 else 'W'}"

            alt_val = _rational_to_float(gps_ifd.get(GPS_ALTITUDE))
            if alt_val is not None:
                alt_ref = gps_ifd.get(GPS_ALTITUDE_REF, 0)
                if alt_ref == 1:
                    alt_val = -alt_val
                data.altitude_m = alt_val
    except Exception as exc:
        logger.debug("GPS parse error: %s", exc)

    return data
