"""
viewer/ui/filmstrip.py
Horizontal filmstrip panel with async thumbnail population.
Now uses customtkinter.
"""

from __future__ import annotations

import logging
import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional

from PIL import ImageTk

logger = logging.getLogger(__name__)


class FilmstripPanel(ctk.CTkFrame):
    """
    A horizontal strip of image thumbnails beneath the main canvas.
    Thumbnails are inserted asynchronously via on_thumb_ready().
    """

    THUMB_SIZE  = 80
    CELL_PAD    = 4   # padding inside each cell border
    ITEM_GAP    = 10  # gap between cells
    ROW_HEIGHT  = 101
    PANEL_HEIGHT = 80

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        colors: dict,
        on_select: Optional[Callable[[int], None]] = None,
    ) -> None:
        bg = colors["panel"]
        super().__init__(parent, fg_color=bg, height=self.PANEL_HEIGHT)
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._colors = colors
        self._on_select = on_select
        self._files: list[str] = []
        self._current: int = -1
        self._thumb_images: dict[int, ImageTk.PhotoImage] = {}
        self._x_offset: int = 10

        # Canvas
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, height=self.ROW_HEIGHT)
        self._canvas.pack(side=ctk.TOP, fill=ctk.BOTH, expand=True)

        # Custom scrollbar
        self._scroll_bg = ctk.CTkFrame(self, fg_color="#1e1e24", height=6)
        self._scroll_bg.pack(side=ctk.BOTTOM, fill=ctk.X)
        self._scroll_bg.pack_propagate(False)
        self._scroll_thumb = ctk.CTkFrame(self._scroll_bg, fg_color="#666677", height=6)

        self._canvas.config(xscrollcommand=self._update_scrollbar)
        self._canvas.bind("<MouseWheel>",      self._on_mousewheel)
        self._canvas.bind("<Shift-MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Configure>",       self._on_resize)
        self._scroll_bg.bind("<Button-1>",   self._on_drag)
        self._scroll_bg.bind("<B1-Motion>",  self._on_drag)
        self._scroll_thumb.bind("<Button-1>",  self._on_drag)
        self._scroll_thumb.bind("<B1-Motion>", self._on_drag)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_files(self, files: list[str], current: int = 0) -> None:
        """Rebuild the filmstrip for a new file list."""
        self._files = files
        self._current = current
        self._thumb_images.clear()
        self._build_placeholders()

    def on_thumb_ready(self, idx: int, img) -> None:
        """Call from main thread when a thumbnail PIL image is ready."""
        if idx >= len(self._files):
            return
        tk_img = ImageTk.PhotoImage(img)
        self._thumb_images[idx] = tk_img  # Keep reference

        cx = self._cell_x(idx) + self.CELL_PAD + self.THUMB_SIZE // 2
        cy = self.CELL_PAD + self.THUMB_SIZE // 2 + 10

        img_id = self._canvas.create_image(cx, cy, image=tk_img, anchor=tk.CENTER)
        self._canvas.tag_raise(f"hitbox_{idx}")
        self._canvas.tag_bind(img_id, "<Button-1>", lambda e, i=idx: self._click(i))

    def highlight(self, idx: int) -> None:
        """Update accent border on the current item."""
        self._current = idx
        for i in range(len(self._files)):
            outline = self._colors.get("accent", "#f08060") if i == idx else ""
            self._canvas.itemconfig(f"rect_{i}", outline=outline, width=2)
        self._scroll_to_index(idx)

    def clear(self) -> None:
        self._files = []
        self._current = -1
        self._thumb_images.clear()
        self._canvas.delete("all")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cell_x(self, idx: int) -> int:
        cell_w = self.THUMB_SIZE + self.CELL_PAD * 2
        return self._x_offset + idx * (cell_w + self.ITEM_GAP)

    def _build_placeholders(self) -> None:
        self._canvas.delete("all")
        n = len(self._files)
        if n == 0:
            return

        cell_w = self.THUMB_SIZE + self.CELL_PAD * 2
        total_w = n * (cell_w + self.ITEM_GAP) - self.ITEM_GAP

        # Center if content fits
        self.update_idletasks()
        cw = self._canvas.winfo_width()
        if cw > 1 and total_w < cw:
            self._x_offset = (cw - total_w) // 2
        else:
            self._x_offset = 10

        for i in range(n):
            x = self._cell_x(i)
            y = 10
            # Placeholder rectangle
            self._canvas.create_rectangle(
                x, y, x + cell_w, y + self.THUMB_SIZE + self.CELL_PAD * 2,
                fill="#2a2a32", outline="", width=2,
                tags=f"rect_{i}",
            )
            # Invisible hitbox
            self._canvas.create_rectangle(
                x, y, x + cell_w, y + self.THUMB_SIZE + self.CELL_PAD * 2,
                fill="", outline="",
                tags=f"hitbox_{i}",
            )
            self._canvas.tag_bind(f"rect_{i}",   "<Button-1>", lambda e, idx=i: self._click(idx))
            self._canvas.tag_bind(f"hitbox_{i}", "<Button-1>", lambda e, idx=i: self._click(idx))

        right_edge = self._cell_x(n) + 10
        self._canvas.config(scrollregion=(0, 0, right_edge, self.PANEL_HEIGHT))
        self.highlight(self._current)

    def _click(self, idx: int) -> None:
        if self._on_select:
            self._on_select(idx)

    def _scroll_to_index(self, idx: int) -> None:
        if not self._files:
            return
        cw = self._canvas.winfo_width()
        if cw <= 1:
            cw = 800
        cell_w = self.THUMB_SIZE + self.CELL_PAD * 2
        x = self._cell_x(idx) + cell_w // 2 - cw // 2
        sr = self._canvas.bbox("all")
        if not sr:
            return
        total = sr[2]
        self._canvas.xview_moveto(max(0.0, min(1.0, x / max(1, total))))

    def _update_scrollbar(self, first: str, last: str) -> None:
        f, l = float(first), float(last)
        if f <= 0.0 and l >= 1.0:
            self._scroll_thumb.place_forget()
        else:
            self._scroll_thumb.place(relx=f, rely=0.0, relwidth=l - f, relheight=1.0)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_drag(self, event: tk.Event) -> None:
        bg_w = self._scroll_bg.winfo_width()
        if bg_w == 0:
            return
        frac = (event.x_root - self._scroll_bg.winfo_rootx()) / bg_w
        self._canvas.xview_moveto(frac)

    def _on_resize(self, event: tk.Event) -> None:
        if not self._files:
            return
        cell_w = self.THUMB_SIZE + self.CELL_PAD * 2
        total_w = len(self._files) * (cell_w + self.ITEM_GAP) - self.ITEM_GAP
        if total_w < event.width:
            new_off = (event.width - total_w) // 2
        else:
            new_off = 10
        if new_off != self._x_offset:
            dx = new_off - self._x_offset
            self._canvas.move("all", dx, 0)
            self._x_offset = new_off
            sr = self._canvas.bbox("all")
            if sr:
                self._canvas.config(scrollregion=(0, 0, sr[2] + new_off, self.PANEL_HEIGHT))