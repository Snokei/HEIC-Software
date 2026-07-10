"""
viewer/ui/statusbar.py
Bottom status bar: left controls, image counter, zoom controls.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .widgets import RoundedButton, ToolTip


class StatusBar(tk.Frame):
    """
    Bottom status bar with:
    - Left: Info (sidebar) toggle, Filmstrip toggle, separator, metadata label
    - Center: Image counter  e.g. "3 / 47"
    - Right: Delete, Rotate, Fit, zoom label, ─ slider ＋, Print
    """

    def __init__(
        self,
        parent: tk.Widget,
        colors: dict,
        on_toggle_info: Optional[Callable] = None,
        on_toggle_filmstrip: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        on_rotate: Optional[Callable] = None,
        on_fit: Optional[Callable] = None,
        on_zoom_in: Optional[Callable] = None,
        on_zoom_out: Optional[Callable] = None,
        on_slider: Optional[Callable] = None,
        on_print: Optional[Callable] = None,
        on_slideshow: Optional[Callable] = None,
        on_open_folder: Optional[Callable] = None,
    ) -> None:
        bg = colors["panel"]
        super().__init__(parent, bg=bg, height=46)
        self._colors = colors
        self.pack_propagate(False)

        self.grid_columnconfigure(1, weight=1)

        # ----------------------------------------------------------------
        # Left section
        # ----------------------------------------------------------------
        left = tk.Frame(self, bg=bg)
        left.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        icon_btn = dict(
            height=28,
            radius=5,
            normal_color=bg,
            hover_color=colors["button_hover"],
            fg="white",
            font=("Segoe UI Variable Display", 14),
        )

        self.btn_info = RoundedButton(left, text="ⓘ", width=28, command=on_toggle_info, **icon_btn)
        self.btn_info.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_info, "Image Properties  (I)")

        self.btn_filmstrip = RoundedButton(left, text="🎞", width=28, command=on_toggle_filmstrip, **icon_btn)
        self.btn_filmstrip.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_filmstrip, "Toggle Filmstrip  (F)")

        self.btn_slideshow = RoundedButton(left, text="▶", width=28, command=on_slideshow, **icon_btn)
        self.btn_slideshow.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_slideshow, "Start / Stop Slideshow  (S)")

        self.btn_open_folder = RoundedButton(left, text="📂", width=28, command=on_open_folder, **icon_btn)
        self.btn_open_folder.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_open_folder, "Open Containing Folder")

        # Separator dot
        tk.Label(left, text="•", bg=bg, fg="#666677", font=("Arial", 11)).pack(side=tk.LEFT, padx=6)

        # Metadata label
        self.lbl_metadata = tk.Label(
            left, text="", bg=bg, fg="#aaaaaa",
            font=("Segoe UI Variable Display", 12),
        )
        self.lbl_metadata.pack(side=tk.LEFT, padx=2)

        # ----------------------------------------------------------------
        # Center — image counter
        # ----------------------------------------------------------------
        center = tk.Frame(self, bg=bg)
        center.grid(row=0, column=1, sticky="nsew")

        self.lbl_counter = tk.Label(
            center, text="", bg=bg, fg="#888888",
            font=("Segoe UI Variable Display", 12),
        )
        self.lbl_counter.pack(expand=True)

        # ----------------------------------------------------------------
        # Right section
        # ----------------------------------------------------------------
        right = tk.Frame(self, bg=bg)
        right.grid(row=0, column=2, padx=12, pady=6, sticky="e")

        right_icon = dict(
            height=28,
            radius=5,
            normal_color=bg,
            hover_color=colors["button_hover"],
            fg="white",
            font=("Segoe UI Variable Display", 14),
        )

        self.btn_delete = RoundedButton(right, text="🗑", width=28, command=on_delete, **right_icon)
        self.btn_delete.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_delete, "Move to Recycle Bin  (Del)")

        self.btn_rotate = RoundedButton(right, text="⟳", width=28, command=on_rotate, **right_icon)
        self.btn_rotate.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_rotate, "Rotate 90° clockwise  (R)")

        self.btn_fit = RoundedButton(right, text="⛶", width=28, command=on_fit, **right_icon)
        self.btn_fit.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_fit, "Fit to window  (F key)")

        self.btn_print = RoundedButton(right, text="🖨", width=28, command=on_print, **right_icon)
        self.btn_print.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_print, "Print  (Ctrl+P)")

        # Thin separator
        tk.Label(right, text="│", bg=bg, fg="#44444f", font=("Arial", 14)).pack(side=tk.LEFT, padx=4)

        # Zoom out
        self.btn_zoom_out = RoundedButton(
            right, text="−", width=26, command=on_zoom_out,
            height=26, radius=5,
            normal_color=bg, hover_color=colors["button_hover"],
            fg="white", font=("Segoe UI Variable Display", 16),
        )
        self.btn_zoom_out.pack(side=tk.LEFT, padx=1)

        # Zoom slider
        self.zoom_var = tk.IntVar(value=100)
        self.zoom_slider = tk.Scale(
            right,
            from_=2, to=800,
            orient=tk.HORIZONTAL,
            variable=self.zoom_var,
            bg=bg,
            fg="white",
            highlightthickness=0,
            troughcolor="#3d3d48",
            activebackground=colors.get("accent_hover", "#ff9a7c"),
            sliderlength=10,
            width=8,
            length=100,
            showvalue=0,
            command=on_slider,
        )
        self.zoom_slider.pack(side=tk.LEFT, padx=4)

        # Zoom in
        self.btn_zoom_in = RoundedButton(
            right, text="+", width=26, command=on_zoom_in,
            height=26, radius=5,
            normal_color=bg, hover_color=colors["button_hover"],
            fg="white", font=("Segoe UI Variable Display", 16),
        )
        self.btn_zoom_in.pack(side=tk.LEFT, padx=1)

        # Zoom label (clickable → fit)
        self.lbl_zoom = tk.Label(
            right, text="100%", bg=bg, fg="white",
            font=("Segoe UI Variable Display", 12),
            width=6, cursor="hand2",
        )
        self.lbl_zoom.pack(side=tk.LEFT, padx=4)
        self.lbl_zoom.bind("<Button-1>", lambda e: on_fit() if on_fit else None)
        ToolTip(self.lbl_zoom, "Click to fit to window")

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def update_zoom(self, zoom: float) -> None:
        pct = int(zoom * 100)
        self.lbl_zoom.config(text=f"{pct}%")
        # Update slider without triggering callback
        cmd = self.zoom_slider.cget("command")
        self.zoom_slider.config(command="")
        self.zoom_slider.set(max(2, min(800, pct)))
        self.zoom_slider.config(command=cmd)

    def update_metadata(self, text: str) -> None:
        self.lbl_metadata.config(text=text)

    def update_counter(self, current: int, total: int) -> None:
        if total > 0:
            self.lbl_counter.config(text=f"{current} / {total}")
        else:
            self.lbl_counter.config(text="")

    def set_info_active(self, active: bool) -> None:
        color = self._colors.get("accent", "#f08060") if active else "white"
        self.btn_info.config(fg=color)

    def set_filmstrip_active(self, active: bool) -> None:
        color = self._colors.get("accent", "#f08060") if active else "white"
        self.btn_filmstrip.config(fg=color)

    def set_slideshow_active(self, active: bool) -> None:
        color = self._colors.get("accent", "#f08060") if active else "white"
        self.btn_slideshow.config(fg=color)
