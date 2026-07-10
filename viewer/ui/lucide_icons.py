"""
viewer/ui/lucide_icons.py
Lucide icon rendering engine using pure Python (Pillow + SVG path parsing).
No system-level dependencies needed.
"""

from __future__ import annotations

import logging
from math import ceil, cos, degrees, pi, radians, sin, sqrt, tan
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

logger = logging.getLogger(__name__)

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
# Lucide SVG icon definitions (MIT license — https://lucide.dev)
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
    # The dot is a small diamond instead of a 0.01-unit line (H12.01)
    # which disappears during 4x oversampling + LANCZOS downscale.
    "info": (
        "M12 8V12 "
        "M11 16l1 1 1-1-1-1Z "
        "M22 12C22 17.5228 17.5228 22 12 22"
        "C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2"
        "C17.5228 2 22 6.47715 22 12Z"
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
}

# Cache for rendered icons: key = (name, size, color_hex) -> PhotoImage
_icon_cache: dict[tuple[str, int, str], ImageTk.PhotoImage] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_icon(
    name: str,
    size: int = 24,
    color: str = "#ffffff",
    stroke_width: int = 2,
) -> ImageTk.PhotoImage:
    """
    Return a rendered Lucide icon as a PhotoImage.

    Parameters
    ----------
    name : str
        Lucide icon name (e.g. "chevron-left", "info", "zoom-in").
    size : int
        Desired width/height in pixels.
    color : str
        Hex colour string (e.g. "#ffffff").
    stroke_width : int
        Stroke width in pixels.
    """
    cache_key = (name, size, color)
    cached = _icon_cache.get(cache_key)
    if cached is not None:
        return cached

    path_str = _ICON_PATHS.get(name)
    if path_str is None:
        logger.warning("Unknown Lucide icon: %s", name)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        tk_img = ImageTk.PhotoImage(img)
        _icon_cache[cache_key] = tk_img
        return tk_img

    # Create image with 4x oversampling for anti-aliasing
    scale = 4
    img_size = size * scale
    img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Scale the viewBox (24x24) to image size, with padding
    margin = (2 * scale)
    draw_scale = (img_size - 2 * margin) / 24.0

    # Transform path: apply scaling
    transformed_path = _transform_path(path_str, draw_scale, margin)

    # Draw the path
    _draw_svg_path(draw, transformed_path, color, stroke_width * scale)

    # Downscale for anti-aliasing
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    tk_img = ImageTk.PhotoImage(img)
    _icon_cache[cache_key] = tk_img
    return tk_img


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
    Return a rendered Lucide icon as a PIL Image (RGBA).
    Useful for compositing onto button backgrounds.
    """
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