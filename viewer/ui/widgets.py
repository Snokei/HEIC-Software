"""
viewer/ui/widgets.py
Shared UI primitives: RoundedButton, ToolTip, rounded image helpers.
Extracted from the original monolith and lightly improved.
"""

from __future__ import annotations

import tkinter as tk
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


# ---------------------------------------------------------------------------
# ToolTip
# ---------------------------------------------------------------------------

class ToolTip:
    """Hover tooltip shown below a widget."""

    _DELAY_MS = 600  # Wait before showing

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip_window: Optional[tk.Toplevel] = None
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

        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#252528",
            foreground="#e8e8e8",
            relief=tk.FLAT,
            font=("Segoe UI Variable Display", 9),
            padx=8,
            pady=4,
        )
        label.pack()
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
# RoundedButton
# ---------------------------------------------------------------------------

class RoundedButton(tk.Button):
    """
    A tk.Button with a PIL-rendered rounded-rectangle background image.
    The background is blended against the parent's background color so
    rounded corners appear seamless.
    """

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        width: int,
        height: int,
        radius: int,
        normal_color: str,
        hover_color: str,
        fg: str,
        hover_fg: Optional[str] = None,
        command: Optional[Callable] = None,
        font: Tuple = ("Segoe UI Variable Display", 9),
    ) -> None:
        self._width = width
        self._height = height
        self._radius = radius
        self._normal_color = normal_color
        self._hover_color = hover_color
        self._fg = fg
        self._hover_fg = hover_fg or fg

        parent_bg = parent.cget("bg")

        self._img_normal = make_rounded_rect_image(width, height, radius, normal_color, parent_bg)
        self._img_hover  = make_rounded_rect_image(width, height, radius, hover_color,  parent_bg)

        super().__init__(
            parent,
            text=text,
            image=self._img_normal,
            compound="center",
            fg=fg,
            activeforeground=self._hover_fg,
            bg=parent_bg,
            activebackground=parent_bg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            command=command,
            font=font,
            cursor="hand2",
        )

        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event=None) -> None:
        self.config(image=self._img_hover, fg=self._hover_fg)

    def _on_leave(self, _event=None) -> None:
        self.config(image=self._img_normal, fg=self._fg)

    def set_active(self, active: bool, active_color: str = "#f08060") -> None:
        """Visually mark this button as toggled on/off."""
        if active:
            self.config(fg=active_color)
        else:
            self.config(fg=self._fg)


# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------

def make_separator(parent: tk.Widget, bg: str, horizontal: bool = True) -> tk.Frame:
    """Return a 1px separator frame."""
    if horizontal:
        return tk.Frame(parent, height=1, bg=bg)
    return tk.Frame(parent, width=1, bg=bg)
