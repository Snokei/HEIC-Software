"""
viewer/ui/statusbar.py
Bottom status bar: left controls, image counter, zoom controls.
Now uses customtkinter.
"""

from __future__ import annotations

import customtkinter as ctk
from typing import Callable, Optional

from .lucide_icons import get_icon_pil
from .widgets import ToolTip, make_button_image_with_icon


class StatusBar(ctk.CTkFrame):
    """
    Bottom status bar with:
    - Left: Info (sidebar) toggle, Filmstrip toggle, separator, metadata label
    - Center: Image counter  e.g. "3 / 47"
    - Right: Delete, Rotate, Fit, zoom label, ─ slider ＋, Print
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
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
        super().__init__(parent, fg_color=bg, height=46)
        self._colors = colors
        self.pack_propagate(False)

        self.grid_columnconfigure(1, weight=1)

        # ----------------------------------------------------------------
        # Left section
        # ----------------------------------------------------------------
        left = ctk.CTkFrame(self, fg_color=bg)
        left.grid(row=0, column=0, padx=12, pady=6, sticky="w")

        # Info button with SVG icon
        info_icon_pil = get_icon_pil("info", size=26, color="#ffffff")
        info_icon_active_pil = get_icon_pil("info", size=26, color=self._colors.get("accent", "#f08060"))

        self._info_img_normal = make_button_image_with_icon(
            28, 28, 5, bg, bg, info_icon_pil,
        )
        self._info_img_hover = make_button_image_with_icon(
            28, 28, 5, colors["button_hover"], bg, info_icon_pil,
        )
        self._info_img_active = make_button_image_with_icon(
            28, 28, 5, bg, bg, info_icon_active_pil,
        )
        self._info_img_active_hover = make_button_image_with_icon(
            28, 28, 5, colors["button_hover"], bg, info_icon_active_pil,
        )

        self.btn_info = ctk.CTkButton(
            left, text="", width=28, height=28,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", command=on_toggle_info,
            font=("Segoe UI Variable Display", 14),
            corner_radius=5, image=self._info_img_normal,
        )
        self.btn_info.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_info, "Image Properties  (I)")

        self.btn_filmstrip = ctk.CTkButton(
            left, text="🎞", width=28, height=28,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", command=on_toggle_filmstrip,
            font=("Segoe UI Variable Display", 14),
            corner_radius=5,
        )
        self.btn_filmstrip.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_filmstrip, "Toggle Filmstrip  (F)")

        self.btn_slideshow = ctk.CTkButton(
            left, text="▶", width=28, height=28,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", command=on_slideshow,
            font=("Segoe UI Variable Display", 14),
            corner_radius=5,
        )
        self.btn_slideshow.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_slideshow, "Start / Stop Slideshow  (S)")

        self.btn_open_folder = ctk.CTkButton(
            left, text="📂", width=28, height=28,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", command=on_open_folder,
            font=("Segoe UI Variable Display", 14),
            corner_radius=5,
        )
        self.btn_open_folder.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_open_folder, "Open Containing Folder")

        # Separator dot
        ctk.CTkLabel(left, text="•", text_color="#666677", font=("Arial", 11)).pack(side=ctk.LEFT, padx=6)

        # Metadata label
        self.lbl_metadata = ctk.CTkLabel(
            left, text="", text_color="#aaaaaa",
            font=("Segoe UI Variable Display", 12),
        )
        self.lbl_metadata.pack(side=ctk.LEFT, padx=2)

        # ----------------------------------------------------------------
        # Center — image counter
        # ----------------------------------------------------------------
        center = ctk.CTkFrame(self, fg_color=bg)
        center.grid(row=0, column=1, sticky="nsew")

        self.lbl_counter = ctk.CTkLabel(
            center, text="", text_color="#888888",
            font=("Segoe UI Variable Display", 12),
        )
        self.lbl_counter.pack(expand=True)

        # ----------------------------------------------------------------
        # Right section
        # ----------------------------------------------------------------
        right = ctk.CTkFrame(self, fg_color=bg)
        right.grid(row=0, column=2, padx=12, pady=6, sticky="e")

        btn_style = dict(
            height=28, width=28,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white",
            font=("Segoe UI Variable Display", 14),
            corner_radius=5,
        )

        self.btn_delete = ctk.CTkButton(right, text="🗑", command=on_delete, **btn_style)
        self.btn_delete.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_delete, "Move to Recycle Bin  (Del)")

        self.btn_rotate = ctk.CTkButton(right, text="⟳", command=on_rotate, **btn_style)
        self.btn_rotate.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_rotate, "Rotate 90° clockwise  (R)")

        self.btn_fit = ctk.CTkButton(right, text="⛶", command=on_fit, **btn_style)
        self.btn_fit.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_fit, "Fit to window  (F key)")

        self.btn_print = ctk.CTkButton(right, text="🖨", command=on_print, **btn_style)
        self.btn_print.pack(side=ctk.LEFT, padx=2)
        ToolTip(self.btn_print, "Print  (Ctrl+P)")

        # Thin separator
        ctk.CTkLabel(right, text="│", text_color="#44444f", font=("Arial", 14)).pack(side=ctk.LEFT, padx=4)

        # Zoom out
        self.btn_zoom_out = ctk.CTkButton(
            right, text="−", width=26, height=26, command=on_zoom_out,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", font=("Segoe UI Variable Display", 16),
            corner_radius=5,
        )
        self.btn_zoom_out.pack(side=ctk.LEFT, padx=1)

        # Zoom slider
        self.zoom_var = ctk.IntVar(value=100)
        self.zoom_slider = ctk.CTkSlider(
            right,
            from_=2, to=800,
            orientation="horizontal",
            variable=self.zoom_var,
            fg_color="#3d3d48",
            button_color=colors.get("accent_hover", "#ff9a7c"),
            button_hover_color=colors.get("accent", "#f08060"),
            height=8,
            width=100,
            command=on_slider,
        )
        self.zoom_slider.pack(side=ctk.LEFT, padx=4)

        # Zoom in
        self.btn_zoom_in = ctk.CTkButton(
            right, text="+", width=26, height=26, command=on_zoom_in,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", font=("Segoe UI Variable Display", 16),
            corner_radius=5,
        )
        self.btn_zoom_in.pack(side=ctk.LEFT, padx=1)

        # Zoom label (clickable → fit)
        self.lbl_zoom = ctk.CTkLabel(
            right, text="100%", text_color="white",
            font=("Segoe UI Variable Display", 12),
            width=6, cursor="hand2",
        )
        self.lbl_zoom.pack(side=ctk.LEFT, padx=4)
        self.lbl_zoom.bind("<Button-1>", lambda e: on_fit() if on_fit else None)
        ToolTip(self.lbl_zoom, "Click to fit to window")

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def update_zoom(self, zoom: float) -> None:
        pct = int(zoom * 100)
        self.lbl_zoom.configure(text=f"{pct}%")
        # Update slider without triggering callback
        cmd = self.zoom_slider.cget("command")
        self.zoom_slider.configure(command="")
        self.zoom_slider.set(max(2, min(800, pct)))
        self.zoom_slider.configure(command=cmd)

    def update_metadata(self, text: str) -> None:
        self.lbl_metadata.configure(text=text)

    def update_counter(self, current: int, total: int) -> None:
        if total > 0:
            self.lbl_counter.configure(text=f"{current} / {total}")
        else:
            self.lbl_counter.configure(text="")

    def set_info_active(self, active: bool) -> None:
        if active:
            self.btn_info.configure(image=self._info_img_active)
        else:
            self.btn_info.configure(image=self._info_img_normal)

    def set_filmstrip_active(self, active: bool) -> None:
        color = self._colors.get("accent", "#f08060") if active else "white"
        self.btn_filmstrip.configure(text_color=color)

    def set_slideshow_active(self, active: bool) -> None:
        color = self._colors.get("accent", "#f08060") if active else "white"
        self.btn_slideshow.configure(text_color=color)