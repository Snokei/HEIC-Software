"""
viewer/ui/sidebar.py
Right-side info/EXIF drawer panel.
"""

from __future__ import annotations

import datetime
import os
import tkinter as tk
from typing import Callable, Optional

from PIL import Image

from ..exif_reader import ExifData
from .widgets import RoundedButton, ToolTip, make_rounded_rect_image, make_rounded_segmented_image


def _get_file_size_str(path: str) -> str:
    try:
        b = os.path.getsize(path)
        if b < 1024:
            return f"{b} B"
        elif b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b / (1024 * 1024):.1f} MB"
    except Exception:
        return ""


class SidebarPanel(tk.Frame):
    """
    Collapsible right-side drawer showing image metadata.
    """

    WIDTH = 340

    def __init__(
        self,
        parent: tk.Widget,
        colors: dict,
        on_close: Optional[Callable] = None,
        on_copy_path: Optional[Callable[[str], None]] = None,
        on_open_folder: Optional[Callable[[str], None]] = None,
    ) -> None:
        bg = colors["panel"]
        super().__init__(parent, bg=bg, width=self.WIDTH)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._colors = colors
        self._on_copy_path = on_copy_path
        self._on_open_folder = on_open_folder

        # Header
        header = tk.Frame(self, bg=bg)
        header.pack(fill=tk.X, padx=16, pady=(14, 8))

        tk.Label(
            header, text="Info", bg=bg, fg="white",
            font=("Segoe UI Variable Display", 13, "bold"),
        ).pack(side=tk.LEFT)

        RoundedButton(
            header, text="✕", width=26, height=26, radius=5,
            normal_color=bg, hover_color=colors["button_hover"],
            fg="white", command=on_close,
        ).pack(side=tk.RIGHT)

        # Scrollable content
        self._content = tk.Frame(self, bg=bg)
        self._content.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # Shared image references (keep alive)
        self._img_refs: list = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate(
        self,
        file_path: str,
        image: Optional[Image.Image],
        exif: Optional[ExifData],
    ) -> None:
        """Rebuild sidebar content for the given image."""
        # Clear
        for w in self._content.winfo_children():
            w.destroy()
        self._img_refs.clear()

        if not image or not file_path:
            tk.Label(
                self._content, text="No photo loaded.",
                bg=self._colors["panel"], fg="#888888",
                font=("Segoe UI Variable Display", 10),
            ).pack(pady=20)
            return

        bg    = self._colors["panel"]
        box_bg    = "#202026"
        box_border = "#2f2f3d"
        BOX_W = 300
        BOX_H = 36
        RADIUS = 6
        BW    = 1

        def _ref(img):
            self._img_refs.append(img)
            return img

        def row(build_fn):
            r = tk.Frame(self._content, bg=bg)
            r.pack(fill=tk.X, pady=6)
            build_fn(r)

        def section_label(parent, text):
            tk.Label(
                parent, text=text, bg=bg, fg="white",
                font=("Segoe UI Variable Display", 10, "bold"),
                anchor="w",
            ).pack(fill=tk.X)

        def info_label(parent, text):
            tk.Label(
                parent, text=text, bg=bg, fg="#888888",
                font=("Segoe UI Variable Display", 9),
                anchor="w", justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(2, 0))

        def segmented_box(parent, dividers=None):
            img = make_rounded_segmented_image(
                BOX_W, BOX_H, RADIUS, box_bg, box_border, BW,
                dividers or [], bg,
            )
            _ref(img)
            lbl = tk.Label(parent, image=img, bg=bg, borderwidth=0, highlightthickness=0)
            lbl.pack(fill=tk.X)
            lbl.image = img
            return lbl

        # --- Filename ---
        def _filename(parent):
            lbl_bg = segmented_box(parent)
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            e = tk.Entry(
                lbl_bg, bg=box_bg, fg="white", relief="flat",
                insertbackground="white",
                font=("Segoe UI Variable Display", 10), justify=tk.CENTER,
            )
            e.insert(0, file_name)
            e.place(x=10, y=0, width=BOX_W - 20, height=BOX_H)
            e.config(state="readonly", readonlybackground=box_bg)
        row(_filename)

        # --- Date / Time ---
        dt = exif.datetime_taken if exif else None
        if dt is None:
            try:
                mtime = os.path.getmtime(file_path)
                dt = datetime.datetime.fromtimestamp(mtime)
            except Exception:
                dt = None

        if dt:
            def _date(parent):
                lbl_bg = segmented_box(parent, [0.15, 0.73])
                for text, x, w in [
                    (str(dt.day), 2, 41),
                    (dt.strftime("%B"), 47, 170),
                    (str(dt.year), 222, 75),
                ]:
                    tk.Label(lbl_bg, text=text, bg=box_bg, fg="white",
                             font=("Segoe UI Variable Display", 10), anchor="center"
                             ).place(x=x, y=2, width=w, height=BOX_H - 4)
            row(_date)

            def _time(parent):
                lbl_bg = segmented_box(parent, [0.5])
                tk.Label(lbl_bg, text=str(dt.hour).zfill(2), bg=box_bg, fg="white",
                         font=("Segoe UI Variable Display", 10), anchor="center"
                         ).place(x=2, y=2, width=145, height=BOX_H - 4)
                tk.Label(lbl_bg, text=dt.strftime("%M"), bg=box_bg, fg="white",
                         font=("Segoe UI Variable Display", 10), anchor="center"
                         ).place(x=152, y=2, width=145, height=BOX_H - 4)
            row(_time)

        # Divider
        tk.Frame(self._content, height=1, bg="#2a2a32").pack(fill=tk.X, pady=8)

        # --- Size Info ---
        def _size(parent):
            section_label(parent, "Size Info")
            w, h = image.size
            size_str = _get_file_size_str(file_path)
            dpi_info = image.info.get("dpi", (72, 72))
            try:
                dpi_val = int(dpi_info[0])
            except Exception:
                dpi_val = 72
            bit_depth = exif.bit_depth if exif else 24
            info_label(parent, f"{w} × {h}    {size_str}    {dpi_val} dpi    {bit_depth}-bit")
        row(_size)

        # --- Camera / EXIF ---
        if exif and (exif.make or exif.model):
            def _camera(parent):
                section_label(parent, "Camera")
                parts = [exif.make, exif.model]
                if exif.lens_model:
                    parts.append(f"({exif.lens_model})")
                info_label(parent, "  ".join(p for p in parts if p))

                settings = [exif.focal_length_mm, exif.aperture, exif.exposure_time,
                            exif.iso, exif.exposure_bias, exif.flash]
                line2 = "   ".join(s for s in settings if s)
                if line2:
                    info_label(parent, line2)

                extra = [exif.white_balance, exif.metering_mode]
                line3 = "   ".join(s for s in extra if s)
                if line3:
                    info_label(parent, line3)
            row(_camera)

        # --- GPS ---
        if exif and exif.gps_string:
            def _gps(parent):
                section_label(parent, "Location")
                gps_row = tk.Frame(parent, bg=bg)
                gps_row.pack(fill=tk.X, pady=(2, 0))
                tk.Label(
                    gps_row, text=exif.gps_string,
                    bg=bg, fg="#888888",
                    font=("Segoe UI Variable Display", 9), anchor="w",
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)
                if exif.altitude_m is not None:
                    info_label(parent, f"Altitude: {exif.altitude_m:.0f} m")
            row(_gps)

        # --- Color profile ---
        if exif and (exif.icc_profile_name or exif.color_space):
            def _color(parent):
                section_label(parent, "Color Profile")
                profile = exif.icc_profile_name or exif.color_space
                info_label(parent, profile)
            row(_color)

        # --- File Path ---
        def _filepath(parent):
            section_label(parent, "File Path")
            path_row = tk.Frame(parent, bg=bg)
            path_row.pack(fill=tk.X, pady=(2, 0))

            tk.Label(
                path_row, text=file_path, bg=bg, fg=self._colors.get("accent", "#f08060"),
                font=("Segoe UI Variable Display", 9),
                anchor="w", justify=tk.LEFT, wraplength=230,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

            btn_frame = tk.Frame(path_row, bg=bg)
            btn_frame.pack(side=tk.RIGHT)

            copy_btn = RoundedButton(
                btn_frame, text="⎘", width=24, height=24, radius=4,
                normal_color=bg, hover_color=self._colors["button_hover"],
                fg="white",
                command=lambda: self._on_copy_path(file_path) if self._on_copy_path else None,
                font=("Segoe UI Variable Display", 9),
            )
            copy_btn.pack()
            ToolTip(copy_btn, "Copy path")

            open_btn = RoundedButton(
                btn_frame, text="📂", width=24, height=24, radius=4,
                normal_color=bg, hover_color=self._colors["button_hover"],
                fg="white",
                command=lambda: self._on_open_folder(file_path) if self._on_open_folder else None,
                font=("Segoe UI Variable Display", 9),
            )
            open_btn.pack(pady=(4, 0))
            ToolTip(open_btn, "Open containing folder")
        row(_filepath)
