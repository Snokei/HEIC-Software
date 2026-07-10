"""
viewer/ui/widgets.py
Shared UI primitives: ToolTip, rounded image helpers.
Now uses customtkinter as the base for all widgets.
"""

from __future__ import annotations

import customtkinter as ctk
from typing import Callable, Optional, Tuple

from PIL import Image, ImageDraw, ImageTk


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def make_rounded_rect_image(
    width: int,
    height: int,
    radius: int,
    bg_color: str,
    parent_bg: str,
) -> ctk.CTkImage:
    """Create a rounded-rectangle PIL image blended against *parent_bg*."""
    render_scale = 2
    w_scaled = width * render_scale
    h_scaled = height * render_scale
    r_scaled = radius * render_scale

    img = Image.new("RGBA", (w_scaled, h_scaled), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (0, 0, w_scaled - 1, h_scaled - 1),
        radius=r_scaled,
        fill=bg_color,
    )
    return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))


def make_rounded_segmented_image(
    width: int,
    height: int,
    radius: int,
    fill_color: str,
    border_color: str,
    border_width: int,
    dividers: list[float],
    parent_bg: str,
) -> ctk.CTkImage:
    """
    Create a rounded rectangle with optional vertical divider lines.
    *dividers* is a list of relative x positions (0.0–1.0).
    """
    render_scale = 2
    w_scaled = width * render_scale
    h_scaled = height * render_scale
    r_scaled = radius * render_scale
    bw_scaled = border_width * render_scale

    img = Image.new("RGBA", (w_scaled, h_scaled), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (0, 0, w_scaled - 1, h_scaled - 1),
        radius=r_scaled,
        fill=fill_color,
        outline=border_color,
        width=bw_scaled,
    )
    for d in dividers:
        x = int(w_scaled * d)
        draw.line(
            (x, bw_scaled, x, h_scaled - 1 - bw_scaled),
            fill=border_color,
            width=bw_scaled,
        )
    return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))


def make_button_image_with_icon(
    width: int,
    height: int,
    radius: int,
    bg_color: str,
    parent_bg: str,
    icon_pil: Image.Image,
) -> ctk.CTkImage:
    """
    Create a rounded-rectangle button image with a PIL icon composited on top,
    centred within the button.
    """
    render_scale = 2
    w_scaled = width * render_scale
    h_scaled = height * render_scale
    r_scaled = radius * render_scale

    img = Image.new("RGBA", (w_scaled, h_scaled), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (0, 0, w_scaled - 1, h_scaled - 1),
        radius=r_scaled,
        fill=bg_color,
    )
    
    # Scale icon to match render_scale
    iw, ih = icon_pil.size
    icon_scaled = icon_pil.resize((iw * render_scale, ih * render_scale), Image.Resampling.LANCZOS)

    # Centre the icon
    iw_s, ih_s = icon_scaled.size
    x = (w_scaled - iw_s) // 2
    y = (h_scaled - ih_s) // 2
    if icon_scaled.mode == "RGBA":
        img.paste(icon_scaled, (x, y), icon_scaled)
    else:
        img.paste(icon_scaled, (x, y))
    return ctk.CTkImage(light_image=img, dark_image=img, size=(width, height))


# ---------------------------------------------------------------------------
# ToolTip
# ---------------------------------------------------------------------------

class ToolTip:
    """Hover tooltip shown below a widget."""

    _DELAY_MS = 600  # Wait before showing

    def __init__(self, widget: ctk.CTkBaseClass | ctk.windows.ctk_tk.CTk, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip_window: Optional[ctk.CTkToplevel] = None
        self._after_id: Optional[str] = None
        widget.bind("<Enter>", self._schedule_show, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def _schedule_show(self, event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self._DELAY_MS, self._show)

    def _show(self) -> None:
        if self._tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 50
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tw.configure(fg_color="#252528")

        label = ctk.CTkLabel(
            tw,
            text=self.text,
            justify="left",
            text_color="#e8e8e8",
            font=("Segoe UI Variable Display", 12),
        )
        label.pack(padx=8, pady=4)
        self._tip_window = tw

    def _cancel(self, event=None) -> None:
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        tw = self._tip_window
        self._tip_window = None
        if tw:
            tw.destroy()

    def update_text(self, text: str) -> None:
        self.text = text


# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------

def make_separator(parent: ctk.CTkBaseClass, bg: str, horizontal: bool = True) -> ctk.CTkFrame:
    """Return a 1px separator frame."""
    if horizontal:
        return ctk.CTkFrame(parent, height=1, fg_color=bg)
    return ctk.CTkFrame(parent, width=1, fg_color=bg)