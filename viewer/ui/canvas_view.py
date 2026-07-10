"""
viewer/ui/canvas_view.py
Zoomable, pannable image canvas with progressive rendering.
Now uses customtkinter.

Strategy:
  1. On zoom/resize: immediately show a fast BILINEAR preview
  2. Schedule a LANCZOS re-render 120 ms later (debounced)
  3. Apply UnsharpMask only on the final LANCZOS pass
"""

from __future__ import annotations

import logging
import tkinter as tk
import customtkinter as ctk
from typing import Callable, Optional, Tuple

from PIL import Image, ImageFilter, ImageTk

logger = logging.getLogger(__name__)

ZOOM_MIN = 0.02
ZOOM_MAX = 16.0


class ZoomableCanvas(ctk.CTkFrame):
    """
    A self-contained frame containing a scrollable Canvas for image display.
    Exposes a simple API used by HEICViewerApp.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        bg: str = "#1b1b22",
        on_resize: Optional[Callable] = None,
        on_double_click: Optional[Callable] = None,
        on_zoom_change: Optional[Callable[[float], None]] = None,
    ) -> None:
        super().__init__(parent, fg_color=bg)
        self._bg = bg
        self._on_resize_cb = on_resize
        self._on_double_click_cb = on_double_click
        self._on_zoom_change_cb = on_zoom_change

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Canvas
        self._canvas = tk.Canvas(
            self,
            bg=bg,
            highlightthickness=0,
            cursor="",
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # State
        self._original: Optional[Image.Image] = None
        self._zoom: float = 1.0
        self._view_mode: str = "fit"  # "fit" | "manual"
        self._canvas_w: int = 0
        self._canvas_h: int = 0
        self._tk_image: Optional[ImageTk.PhotoImage] = None
        self._img_id: Optional[int] = None
        self._sharpen_after_id: Optional[str] = None

        # Pan state
        self._pan_start_x: int = 0
        self._pan_start_y: int = 0

        # Bindings
        self._canvas.bind("<Configure>",       self._on_canvas_configure)
        self._canvas.bind("<ButtonPress-1>",   self._on_pan_start)
        self._canvas.bind("<B1-Motion>",       self._on_pan)
        self._canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self._canvas.bind("<MouseWheel>",      self._on_mousewheel)
        self._canvas.bind("<Button-4>",        self._on_mousewheel)  # Linux scroll up
        self._canvas.bind("<Button-5>",        self._on_mousewheel)  # Linux scroll down
        self._canvas.bind("<Double-Button-1>", self._on_double_click)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def canvas(self) -> tk.Canvas:
        """Expose underlying canvas for overlay widgets."""
        return self._canvas

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_image(self, image: Image.Image) -> None:
        """Display a new image, reset zoom to fit."""
        self._original = image
        self._view_mode = "fit"
        self._zoom = 1.0
        self._render()

    def clear(self) -> None:
        """Remove the displayed image."""
        self._original = None
        self._tk_image = None
        self._canvas.delete("all")

    def zoom_to_fit(self) -> None:
        if not self._original:
            return
        self._view_mode = "fit"
        self._render()

    def zoom_to_100(self) -> None:
        if not self._original:
            return
        self._zoom_to_scale(1.0)

    def zoom_in(self) -> None:
        if not self._original:
            return
        cw, ch = self._canvas_size()
        self._zoom_to_scale(
            min(self._zoom * 1.25, ZOOM_MAX),
            anchor=(cw // 2, ch // 2),
        )

    def zoom_out(self) -> None:
        if not self._original:
            return
        cw, ch = self._canvas_size()
        self._zoom_to_scale(
            max(self._zoom * 0.8, ZOOM_MIN),
            anchor=(cw // 2, ch // 2),
        )

    def set_zoom(self, factor: float) -> None:
        """Set zoom to an explicit factor (1.0 = 100%)."""
        if not self._original:
            return
        self._zoom_to_scale(max(ZOOM_MIN, min(factor, ZOOM_MAX)))

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _canvas_size(self) -> Tuple[int, int]:
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        return (max(w, 100), max(h, 100))

    def _compute_fit_zoom(self) -> float:
        if not self._original:
            return 1.0
        cw, ch = self._canvas_size()
        iw, ih = self._original.size
        ratio = min(cw / iw, ch / ih)
        return min(ratio, 1.0)

    def _render(self, quality: str = "fast") -> None:
        """Render the current image at current zoom. quality='fast'|'hq'."""
        if not self._original:
            return

        if self._view_mode == "fit":
            self._zoom = self._compute_fit_zoom()
            if self._zoom <= 0:
                self._zoom = 1.0

        cw, ch = self._canvas_size()
        iw, ih = self._original.size
        new_w = max(1, int(iw * self._zoom))
        new_h = max(1, int(ih * self._zoom))

        # Choose resampling based on quality pass
        if quality == "hq":
            resampler = Image.Resampling.LANCZOS
            apply_sharpen = True
        else:
            resampler = Image.Resampling.BILINEAR
            apply_sharpen = False

        resized = self._original.resize((new_w, new_h), resampler)

        if apply_sharpen and self._zoom < 1.0:
            try:
                resized = resized.filter(
                    ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=3)
                )
            except Exception:
                pass

        self._tk_image = ImageTk.PhotoImage(resized)

        x_off = max(0, (cw - new_w) // 2)
        y_off = max(0, (ch - new_h) // 2)

        self._canvas.delete("all")
        self._img_id = self._canvas.create_image(
            x_off, y_off, anchor=tk.NW, image=self._tk_image
        )

        scroll_w = max(new_w, cw)
        scroll_h = max(new_h, ch)
        self._canvas.config(scrollregion=(0, 0, scroll_w, scroll_h))

        if self._on_zoom_change_cb:
            self._on_zoom_change_cb(self._zoom)

        # Schedule high-quality pass if we just did a fast one
        if quality == "fast":
            self._schedule_hq_render()

    def _schedule_hq_render(self) -> None:
        """Debounce: replace fast preview with LANCZOS after 120 ms."""
        if self._sharpen_after_id:
            self.after_cancel(self._sharpen_after_id)
        self._sharpen_after_id = self.after(120, lambda: self._render("hq"))

    def _zoom_to_scale(
        self,
        new_zoom: float,
        anchor: Optional[Tuple[int, int]] = None,
    ) -> None:
        if not self._original:
            return

        old_zoom = self._zoom
        self._zoom = new_zoom
        self._view_mode = "manual"

        cw, ch = self._canvas_size()
        iw, ih = self._original.size

        old_w = int(iw * old_zoom)
        old_h = int(ih * old_zoom)
        new_w = int(iw * new_zoom)
        new_h = int(ih * new_zoom)

        # Compute scroll position to keep anchor point fixed
        target_x_frac = 0.0
        target_y_frac = 0.0
        if anchor:
            ax, ay = anchor
            mx = self._canvas.canvasx(ax)
            my = self._canvas.canvasy(ay)
            old_x_off = max(0, (cw - old_w) // 2)
            old_y_off = max(0, (ch - old_h) // 2)
            rx = mx - old_x_off
            ry = my - old_y_off
            ratio = new_zoom / old_zoom
            new_x_off = max(0, (cw - new_w) // 2)
            new_y_off = max(0, (ch - new_h) // 2)
            new_mx = new_x_off + rx * ratio
            new_my = new_y_off + ry * ratio
            target_left = new_mx - ax
            target_top  = new_my - ay
            sw = max(new_w, cw)
            sh = max(new_h, ch)
            target_x_frac = max(0.0, min(1.0, target_left / sw))
            target_y_frac = max(0.0, min(1.0, target_top  / sh))

        self._render("fast")

        if anchor and (new_w > cw or new_h > ch):
            self._canvas.xview_moveto(target_x_frac)
            self._canvas.yview_moveto(target_y_frac)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if event.width == self._canvas_w and event.height == self._canvas_h:
            return
        self._canvas_w = event.width
        self._canvas_h = event.height
        if self._original:
            self._render("fast")
        if self._on_resize_cb:
            self._on_resize_cb(event)

    def _on_pan_start(self, event: tk.Event) -> None:
        self._canvas.config(cursor="fleur")
        self._canvas.scan_mark(event.x, event.y)

    def _on_pan(self, event: tk.Event) -> None:
        self._canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_pan_end(self, event: tk.Event) -> None:
        self._canvas.config(cursor="")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if not self._original:
            return
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        elif event.num == 5 or event.delta < 0:
            factor = 1 / 1.15
        else:
            return
        new_zoom = max(ZOOM_MIN, min(self._zoom * factor, ZOOM_MAX))
        self._zoom_to_scale(new_zoom, anchor=(event.x, event.y))

    def _on_double_click(self, event: tk.Event) -> None:
        if self._on_double_click_cb:
            self._on_double_click_cb(event)