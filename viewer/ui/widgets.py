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
) -> ImageTk.PhotoImage:
    """Create a rounded-rectangle PIL image blended against *parent_bg*."""
    img = Image.new("RGBA", (width, height), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=bg_color,
    )
    return ImageTk.PhotoImage(img)


def make_rounded_segmented_image(
    width: int,
    height: int,
    radius: int,
    fill_color: str,
    border_color: str,
    border_width: int,
    dividers: list[float],
    parent_bg: str,
) -> ImageTk.PhotoImage:
    """
    Create a rounded rectangle with optional vertical divider lines.
    *dividers* is a list of relative x positions (0.0–1.0).
    """
    img = Image.new("RGBA", (width, height), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=fill_color,
        outline=border_color,
        width=border_width,
    )
    for d in dividers:
        x = int(width * d)
        draw.line(
            (x, border_width, x, height - 1 - border_width),
            fill=border_color,
            width=border_width,
        )
    return ImageTk.PhotoImage(img)


def make_button_image_with_icon(
    width: int,
    height: int,
    radius: int,
    bg_color: str,
    parent_bg: str,
    icon_pil: Image.Image,
) -> ImageTk.PhotoImage:
    """
    Create a rounded-rectangle button image with a PIL icon composited on top,
    centred within the button.
    """
    img = Image.new("RGBA", (width, height), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=bg_color,
    )
    # Centre the icon
    iw, ih = icon_pil.size
    x = (width - iw) // 2
    y = (height - ih) // 2
    if icon_pil.mode == "RGBA":
        img.paste(icon_pil, (x, y), icon_pil)
    else:
        img.paste(icon_pil, (x, y))
    return ImageTk.PhotoImage(img)


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