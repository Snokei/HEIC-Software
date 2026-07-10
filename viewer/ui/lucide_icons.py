"""
viewer/ui/lucide_icons.py
Lucide icon rendering engine using pure Python (Pillow + SVG path parsing).
Supports loading SVG files via the tksvg library for better rendering.
All icons are modern Lucide-style MIT-licensed icons.
"""

from __future__ import annotations

import logging
import os
import tempfile
from math import ceil, cos, degrees, pi, radians, sin, sqrt, tan
from typing import Optional

from PIL import Image, ImageDraw, ImageTk
import customtkinter as ctk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# tksvg — load SVG files as Tk PhotoImages, then convert to PIL
# ---------------------------------------------------------------------------

_HAS_TKSVG = False
try:
    import tksvg
    _HAS_TKSVG = True
except ImportError:
    logger.info("tksvg not installed; falling back to built-in SVG path renderer")


def _load_svg_as_pil(filepath: str, size: int, color: str) -> Optional[Image.Image]:
    """
    Load an SVG file via tksvg, recolor the strokes, and return a PIL Image.
    Returns None if tksvg is unavailable or loading fails.
    """
    if not _HAS_TKSVG:
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            svg_data = f.read()

        # Replace currentColor (used in Lucide SVGs) with the requested color
        svg_data = svg_data.replace("currentColor", color)

        # Auto-compute scale: the SVG viewBox is 24×24; we want it at *size* pixels
        scale = size / 24.0

        svg_img = tksvg.SvgImage(data=svg_data, scale=scale)

        # Convert the Tk PhotoImage to PIL via a temporary PNG file
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_name = tmp.name
        tmp.close()
        try:
            svg_img.write(tmp_name, format="png")
            pil_img = Image.open(tmp_name)
            pil_img.load()
            # Ensure exact size (tksvg may round slightly)
            if pil_img.size != (size, size):
                pil_img = pil_img.resize((size, size), Image.Resampling.LANCZOS)
            return pil_img
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
    except Exception as exc:
        logger.warning("SVG load failed for %s: %s", filepath, exc)
        return None


# ---------------------------------------------------------------------------
# Minimal SVG path parser
# Converts SVG path commands to PIL draw operations.
# Handles the subset of SVG path commands used by Lucide icons.
# ---------------------------------------------------------------------------

class _Point:
    __slots__ = ("x", "y")
    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"({self.x:.1f}, {self.y:.1f})"


def _tokenize_path(path_str: str) -> list[str]:
    """Tokenize an SVG path data string into commands and numbers."""
    tokens: list[str] = []
    i = 0
    while i < len(path_str):
        ch = path_str[i]
        if ch in " \t\n\r,":
            i += 1
            continue
        if ch in "MmZzLlHhVvCcSsQqTtAa":
            tokens.append(ch)
            i += 1
        elif ch == "-" or ch.isdigit() or ch == ".":
            start = i
            # Handle minus signs for negative numbers
            if ch == "-":
                i += 1
                if i < len(path_str) and (path_str[i].isdigit() or path_str[i] == "."):
                    i += 1
            while i < len(path_str) and (path_str[i].isdigit() or path_str[i] == "." or path_str[i] == "e" or path_str[i] == "E" or (path_str[i] == "-" and path_str[i-1] in "eE")):
                i += 1
            tokens.append(path_str[start:i])
        else:
            i += 1
    return tokens


def _parse_number(tokens: list[str], pos: list[int]) -> float:
    """Read the next numeric token."""
    while pos[0] < len(tokens) and tokens[pos[0]] in ("", " ", "  "):
        pos[0] += 1
    if pos[0] >= len(tokens):
        return 0.0
    val = float(tokens[pos[0]])
    pos[0] += 1
    return val


def _draw_svg_path(draw: ImageDraw.ImageDraw, path_str: str, stroke_color, stroke_width: int) -> None:
    """Render an SVG path onto a PIL ImageDraw surface."""
    tokens = _tokenize_path(path_str)
    if not tokens:
        return

    cp = _Point()  # current point
    sp = _Point()  # start point of current subpath
    pp = _Point()  # previous control point (for S/s, T/t)
    pos = [0]

    lines: list[tuple[float, float, float, float]] = []
    points: list[tuple[float, float]] = []

    def _read_point(relative: bool) -> _Point:
        x = _parse_number(tokens, pos)
        y = _parse_number(tokens, pos)
        if relative:
            return _Point(cp.x + x, cp.y + y)
        return _Point(x, y)

    def _read_coords(relative: bool, count: int) -> list[_Point]:
        pts = []
        for _ in range(count):
            pts.append(_read_point(relative))
        return pts

    while pos[0] < len(tokens):
        cmd = tokens[pos[0]]
        pos[0] += 1

        if cmd == "M":  # Move absolute
            pts = _read_coords(False, 1)
            cp = pts[0]
            sp = _Point(cp.x, cp.y)
            pp = _Point(cp.x, cp.y)
            points = [(cp.x, cp.y)]
        elif cmd == "m":  # Move relative
            pts = _read_coords(True, 1)
            cp = pts[0]
            sp = _Point(cp.x, cp.y)
            pp = _Point(cp.x, cp.y)
            points = [(cp.x, cp.y)]
        elif cmd in ("L", "l"):
            relative = cmd == "l"
            while pos[0] < len(tokens) and (tokens[pos[0]] not in "MmZzLlHhVvCcSsQqTtAa" or not tokens[pos[0]][0].isalpha() if tokens[pos[0]][0].isalpha() else False):
                if pos[0] >= len(tokens):
                    break
                # Check if next token starts a new command
                t = tokens[pos[0]]
                if t[0].isalpha() if t else False:
                    break
                pt = _read_point(relative)
                draw.line(
                    (cp.x, cp.y, pt.x, pt.y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = pt
                pp = _Point(cp.x, cp.y)
        elif cmd in ("H", "h"):
            relative = cmd == "h"
            x = _parse_number(tokens, pos)
            if relative:
                x = cp.x + x
            draw.line(
                (cp.x, cp.y, x, cp.y),
                fill=stroke_color, width=stroke_width,
            )
            cp.x = x
            pp = _Point(cp.x, cp.y)
        elif cmd in ("V", "v"):
            relative = cmd == "v"
            y = _parse_number(tokens, pos)
            if relative:
                y = cp.y + y
            draw.line(
                (cp.x, cp.y, cp.x, y),
                fill=stroke_color, width=stroke_width,
            )
            cp.y = y
            pp = _Point(cp.x, cp.y)
        elif cmd == "C":  # Cubic bezier absolute
            pts = _read_coords(False, 3)
            c1, c2, end = pts
            # Approximate bezier with multiple line segments
            for t_val in range(1, 21):
                t = t_val / 20.0
                x = (1-t)**3 * cp.x + 3*(1-t)**2*t * c1.x + 3*(1-t)*t**2 * c2.x + t**3 * end.x
                y = (1-t)**3 * cp.y + 3*(1-t)**2*t * c1.y + 3*(1-t)*t**2 * c2.y + t**3 * end.y
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(c2.x, c2.y)
        elif cmd == "c":  # Cubic bezier relative
            pts = _read_coords(True, 3)
            c1, c2, end = pts
            for t_val in range(1, 21):
                t = t_val / 20.0
                x = (1-t)**3 * cp.x + 3*(1-t)**2*t * c1.x + 3*(1-t)*t**2 * c2.x + t**3 * end.x
                y = (1-t)**3 * cp.y + 3*(1-t)**2*t * c1.y + 3*(1-t)*t**2 * c2.y + t**3 * end.y
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(c2.x, c2.y)
        elif cmd == "Q":  # Quadratic bezier absolute
            pts = _read_coords(False, 2)
            c, end = pts
            for t_val in range(1, 21):
                t = t_val / 20.0
                x = (1-t)**2 * cp.x + 2*(1-t)*t * c.x + t**2 * end.x
                y = (1-t)**2 * cp.y + 2*(1-t)*t * c.y + t**2 * end.y
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(c.x, c.y)
        elif cmd == "q":  # Quadratic bezier relative
            pts = _read_coords(True, 2)
            c, end = pts
            for t_val in range(1, 21):
                t = t_val / 20.0
                x = (1-t)**2 * cp.x + 2*(1-t)*t * c.x + t**2 * end.x
                y = (1-t)**2 * cp.y + 2*(1-t)*t * c.y + t**2 * end.y
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(c.x, c.y)
        elif cmd in ("S", "s"):  # Smooth cubic bezier
            relative = cmd == "s"
            c2 = _read_point(relative)
            end = _read_point(relative)
            # Reflect previous control point
            c1 = _Point(2 * cp.x - pp.x, 2 * cp.y - pp.y)
            for t_val in range(1, 21):
                t = t_val / 20.0
                x = (1-t)**3 * cp.x + 3*(1-t)**2*t * c1.x + 3*(1-t)*t**2 * c2.x + t**3 * end.x
                y = (1-t)**3 * cp.y + 3*(1-t)**2*t * c1.y + 3*(1-t)*t**2 * c2.y + t**3 * end.y
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(c2.x, c2.y)
        elif cmd in ("T", "t"):  # Smooth quadratic bezier
            relative = cmd == "t"
            end = _read_point(relative)
            c = _Point(2 * cp.x - pp.x, 2 * cp.y - pp.y)
            for t_val in range(1, 21):
                t = t_val / 20.0
                x = (1-t)**2 * cp.x + 2*(1-t)*t * c.x + t**2 * end.x
                y = (1-t)**2 * cp.y + 2*(1-t)*t * c.y + t**2 * end.y
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(c.x, c.y)
        elif cmd in ("A", "a"):  # Arc
            relative = cmd == "a"
            rx = _parse_number(tokens, pos)
            ry = _parse_number(tokens, pos)
            x_axis_rot = _parse_number(tokens, pos)
            large_arc = int(_parse_number(tokens, pos))
            sweep = int(_parse_number(tokens, pos))
            end = _read_point(relative)
            # Approximate arc with line segments
            for t_val in range(1, 21):
                t = t_val / 20.0
                angle = t * pi
                x = cp.x + (end.x - cp.x) * (1 - cos(angle)) / 2
                y = cp.y + (end.y - cp.y) * sin(angle) / 2
                draw.line(
                    (cp.x, cp.y, x, y),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(x, y)
            cp = _Point(end.x, end.y)
            pp = _Point(cp.x, cp.y)
        elif cmd in ("Z", "z"):  # Close path
            if points:
                sx, sy = points[0]
                draw.line(
                    (cp.x, cp.y, sx, sy),
                    fill=stroke_color, width=stroke_width,
                )
                cp = _Point(sx, sy)
                pp = _Point(cp.x, cp.y)


# ---------------------------------------------------------------------------
# Modern Lucide SVG icon definitions (MIT license — https://lucide.dev)
# ---------------------------------------------------------------------------

_ICON_PATHS: dict[str, str] = {
    # Navigation
    "chevron-left": "m15 18-6-6 6-6",
    "chevron-right": "m9 18 6-6-6-6",

    # Actions
    "copy": (
        "M8 8v-4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4 "
        "M16 16H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v10Z"
    ),
    "save": (
        "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z "
        "M17 21v-8H7v8 M7 3v5h8"
    ),

    # Status bar left — info icon (circle-i)
    "info": (
        "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z "
        "M12 8v4 M12 16h.01"
    ),
    "images": (
        "M18 22H4a2 2 0 0 1-2-2V6 "
        "M22 18V4a2 2 0 0 0-2-2H8 "
        "M8 18h14 M8 12h14 M8 6h14"
    ),
    "play": "M5 3l14 9-14 9V3z",
    "folder-open": (
        "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z "
        "M2 15h18l-2.47 4.94a2 2 0 0 1-1.78 1.06H4a2 2 0 0 1-2-2Z"
    ),

    # Status bar right
    "trash-2": (
        "M3 6h18 M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6 "
        "M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2 "
        "M10 11v6 M14 11v6"
    ),
    "rotate-ccw": (
        "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8 "
        "M3 3v5h5"
    ),
    "maximize": (
        "M8 3H5a2 2 0 0 0-2 2v3 "
        "M21 8V5a2 2 0 0 0-2-2h-3 "
        "M16 21h3a2 2 0 0 0 2-2v-3 "
        "M3 16v3a2 2 0 0 0 2 2h3"
    ),
    "printer": (
        "M6 9V2h12v7 "
        "M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2 "
        "M6 14h12v8H6z"
    ),

    # Zoom
    "zoom-out": (
        "M11 11m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0 "
        "M21 21l-4.35-4.35 "
        "M8 11h6"
    ),
    "zoom-in": (
        "M11 11m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0 "
        "M21 21l-4.35-4.35 "
        "M11 8v6 M8 11h6"
    ),

    # Close / X
    "x": "M18 6L6 18 M6 6l12 12",

    # File copy (two overlapping documents)
    "files": (
        "M20 7h-3a2 2 0 0 1-2-2V2 "
        "M9 18a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h7l5 5v9a2 2 0 0 1-2 2Z "
        "M15 20v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1"
    ),

    # NEW MODERN ICONS
    # Filmstrip / panels icon
    "film": (
        "M2 8h20 M2 16h20 "
        "M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"
    ),

    # Panel bottom (filmstrip layout)
    "panel-bottom": (
        "M2 4h20 "
        "M2 4v16a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V4"
    ),

    # Panel left open (sidebar toggle)
    "panel-left-open": (
        "M4 2v20 "
        "M4 2h16a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z "
        "M10 10l-3 2 3 2"
    ),

    # Panel left close
    "panel-left-close": (
        "M4 2v20 "
        "M4 2h16a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z "
        "M14 10l3 2-3 2"
    ),

    # External link (open folder location)
    "external-link": (
        "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6 "
        "M15 3h6v6 "
        "M10 14L21 3"
    ),

    # Clipboard copy
    "clipboard-copy": (
        "M8 2h8a2 2 0 0 1 2 2v2 "
        "M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2 "
        "M12 11v6 M9 14l3 3 3-3"
    ),

    # Slideshow / presentation
    "presentation": (
        "M2 3h20 "
        "M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3 "
        "M7 21l5-5 5 5"
    ),

    # Image plus (add files)
    "image-plus": (
        "M21 12v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h8 "
        "M14 21h4 M16 19v4"
    ),

    # Folder plus (add folder)
    "folder-plus": (
        "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z "
        "M12 10v6 M9 13h6"
    ),

    # File edit (save as)
    "file-edit": (
        "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z "
        "M14 2v6h6 "
        "M9 15l3-3 6 6 "
        "M15 18l-3 3"
    ),

    # Fullscreen (fit to window)
    "fullscreen": (
        "M8 3H5a2 2 0 0 0-2 2v3 "
        "M21 8V5a2 2 0 0 0-2-2h-3 "
        "M16 21h3a2 2 0 0 0 2-2v-3 "
        "M3 16v3a2 2 0 0 0 2 2h3"
    ),
}

# Cache for rendered icons: key = (name, size, color_hex) -> CTkImage
_icon_cache: dict[tuple[str, int, str], ctk.CTkImage] = {}

# Path to the assets directory (two levels up from viewer/ui/, then into assets/)
_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_icon(
    name: str,
    size: int = 24,
    color: str = "#ffffff",
    stroke_width: int = 2,
) -> ctk.CTkImage:
    """
    Return a rendered icon as a CTkImage.

    For all icons, this attempts to load native vector SVG files from the assets/ directory
    using tksvg (with 2x size for high-DPI scaling quality), falling back to high-res PIL path rendering.

    Parameters
    ----------
    name : str
        Icon name (e.g. "chevron-left", "info", "zoom-in").
    size : int
        Desired logical width/height in pixels.
    color : str
        Hex colour string (e.g. "#ffffff").
    stroke_width : int
        Stroke width in pixels.
    """
    cache_key = (name, size, color)
    cached = _icon_cache.get(cache_key)
    if cached is not None:
        return cached

    # Render/load at a higher scale for High DPI crispness
    render_scale = 2
    render_size = size * render_scale

    # Try loading from an SVG file in assets/ first using multiple candidate styles
    pascal_name = "".join(part.capitalize() for part in name.split("-"))
    candidates = [
        f"{pascal_name}.svg",
        f"{name.title()}.svg",
        f"{name}.svg",
    ]
    svg_path = None
    for cand in candidates:
        cand_path = os.path.join(_ASSETS_DIR, cand)
        if os.path.isfile(cand_path):
            svg_path = cand_path
            break

    if svg_path is not None:
        pil_img = _load_svg_as_pil(svg_path, render_size, color)
        if pil_img is not None:
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(size, size))
            _icon_cache[cache_key] = ctk_img
            return ctk_img

    # Fall back to built-in path rendering
    path_str = _ICON_PATHS.get(name)
    if path_str is None:
        logger.warning("Unknown Lucide icon: %s", name)
        img = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        _icon_cache[cache_key] = ctk_img
        return ctk_img

    # Create image with 4x oversampling for anti-aliasing (relative to render_size)
    scale = 4
    img_size = render_size * scale
    img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Scale the viewBox (24x24) to image size, with padding
    margin = (2 * scale)
    draw_scale = (img_size - 2 * margin) / 24.0

    # Transform path: apply scaling
    transformed_path = _transform_path(path_str, draw_scale, margin)

    # Draw the path
    _draw_svg_path(draw, transformed_path, color, stroke_width * scale)

    # Downscale to render_size for anti-aliasing
    img = img.resize((render_size, render_size), Image.Resampling.LANCZOS)

    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _icon_cache[cache_key] = ctk_img
    return ctk_img


def _transform_path(path_str: str, scale: float, margin: float) -> str:
    """Scale and translate an SVG path by the given factors."""
    tokens = _tokenize_path(path_str)
    result: list[str] = []
    i = 0

    def _next() -> str:
        nonlocal i
        if i < len(tokens):
            t = tokens[i]
            i += 1
            return t
        return ""

    def _peek() -> str:
        if i < len(tokens):
            return tokens[i]
        return ""

    while i < len(tokens):
        token = _next()
        if token in "MmZzLlHhVvCcSsQqTtAa":
            if token == "Z" or token == "z":
                result.append(token)
            elif token in ("M", "m", "L", "l", "C", "c", "Q", "q", "S", "s", "T", "t"):
                result.append(token)
                while i < len(tokens):
                    # Check if next token is a command letter
                    nxt = _peek()
                    if nxt and nxt[0].isalpha() and len(nxt) == 1:
                        break
                    try:
                        val = float(_next())
                        result.append(str(val * scale + margin))
                    except (ValueError, IndexError):
                        break
            elif token == "H":
                result.append(token)
                if i < len(tokens):
                    try:
                        val = float(_next())
                        result.append(str(val * scale + margin))
                    except (ValueError, IndexError):
                        pass
            elif token == "h":
                result.append(token)
                if i < len(tokens):
                    try:
                        val = float(_next())
                        result.append(str(val * scale))
                    except (ValueError, IndexError):
                        pass
            elif token == "V":
                result.append(token)
                if i < len(tokens):
                    try:
                        val = float(_next())
                        result.append(str(val * scale + margin))
                    except (ValueError, IndexError):
                        pass
            elif token == "v":
                result.append(token)
                if i < len(tokens):
                    try:
                        val = float(_next())
                        result.append(str(val * scale))
                    except (ValueError, IndexError):
                        pass
            elif token in ("A", "a"):
                result.append(token)
                count = 0
                while i < len(tokens) and count < 7:
                    nxt = _peek()
                    if nxt and nxt[0].isalpha() and len(nxt) == 1 and nxt not in "eE" and nxt not in "-.":
                        break
                    try:
                        val = float(_next())
                        if count == 5 or count == 6:  # end point coordinates
                            result.append(str(val * scale + margin))
                        else:
                            result.append(str(val * scale))
                        count += 1
                    except (ValueError, IndexError):
                        break
        else:
            result.append(token)
            i += 1

    return " ".join(result)


def get_icon_pil(
    name: str,
    size: int = 24,
    color: str = "#ffffff",
    stroke_width: int = 2,
) -> Image.Image:
    """
    Return a rendered icon as a PIL Image (RGBA).
    Useful for compositing onto button backgrounds.

    For the "info" icon, this loads assets/Info.svg via tksvg when available.
    All other icons are rendered from the built-in SVG path definitions.
    """
    # Try loading from an SVG file in assets/ first using multiple candidate styles
    pascal_name = "".join(part.capitalize() for part in name.split("-"))
    candidates = [
        f"{pascal_name}.svg",
        f"{name.title()}.svg",
        f"{name}.svg",
    ]
    svg_path = None
    for cand in candidates:
        cand_path = os.path.join(_ASSETS_DIR, cand)
        if os.path.isfile(cand_path):
            svg_path = cand_path
            break

    if svg_path is not None:
        pil_img = _load_svg_as_pil(svg_path, size, color)
        if pil_img is not None:
            return pil_img

    # Fall back to built-in path rendering
    path_str = _ICON_PATHS.get(name)
    if path_str is None:
        logger.warning("Unknown Lucide icon: %s", name)
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))

    scale = 4
    img_size = size * scale
    img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = (2 * scale)
    draw_scale = (img_size - 2 * margin) / 24.0

    transformed_path = _transform_path(path_str, draw_scale, margin)
    _draw_svg_path(draw, transformed_path, color, stroke_width * scale)

    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def clear_cache() -> None:
    """Clear the icon render cache (e.g. on theme change)."""
    _icon_cache.clear()


def prewarm_cache(size: int = 24, color: str = "#ffffff") -> None:
    """Render all known icons at the given size/color for faster first display."""
    for name in _ICON_PATHS:
        get_icon(name, size=size, color=color)