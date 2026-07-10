"""
viewer/ui/sidebar.py
Right-side info/EXIF drawer panel.
Now uses customtkinter.
"""

from __future__ import annotations

import datetime
import os
import customtkinter as ctk
from typing import Callable, Optional

from PIL import Image

from ..exif_reader import ExifData
from .widgets import ToolTip, make_rounded_rect_image, make_rounded_segmented_image


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


class SidebarPanel(ctk.CTkFrame):
    """
    Collapsible right-side drawer showing image metadata.
    """

    WIDTH = 340

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        colors: dict,
        on_close: Optional[Callable] = None,
        on_copy_path: Optional[Callable[[str], None]] = None,
        on_open_folder: Optional[Callable[[str], None]] = None,
    ) -> None:
        bg = colors["panel"]
        super().__init__(parent, fg_color=bg, width=self.WIDTH)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._colors = colors
        self._on_copy_path = on_copy_path
        self._on_open_folder = on_open_folder

        # Header
        header = ctk.CTkFrame(self, fg_color=bg)
        header.pack(fill=ctk.X, padx=16, pady=(14, 8))

        ctk.CTkLabel(
            header, text="Info", text_color="white",
            font=("Segoe UI Variable Display", 16, "bold"),
        ).pack(side=ctk.LEFT)

        self._btn_close = ctk.CTkButton(
            header, text="✕", width=26, height=26,
            fg_color=bg, hover_color=colors["button_hover"],
            text_color="white", command=on_close,
            font=("Segoe UI Variable Display", 14),
            corner_radius=5,
        )
        self._btn_close.pack(side=ctk.RIGHT)

        # Scrollable content
        self._content = ctk.CTkFrame(self, fg_color=bg)
        self._content.pack(fill=ctk.BOTH, expand=True, padx=16, pady=4)

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
            ctk.CTkLabel(
                self._content, text="No photo loaded.",
                text_color="#888888",
                font=("Segoe UI Variable Display", 12),
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
            r = ctk.CTkFrame(self._content, fg_color=bg)
            r.pack(fill=ctk.X, pady=6)
            build_fn(r)

        def section_label(parent, text):
            ctk.CTkLabel(
                parent, text=text, text_color="white",
                font=("Segoe UI Variable Display", 12, "bold"),
                anchor="w",
            ).pack(fill=ctk.X)

        def info_label(parent, text):
            ctk.CTkLabel(
                parent, text=text, text_color="#888888",
                font=("Segoe UI Variable Display", 12),
                anchor="w", justify="left",
            ).pack(fill=ctk.X, pady=(2, 0))

        def segmented_box(parent, dividers=None):
            img = make_rounded_segmented_image(
                BOX_W, BOX_H, RADIUS, box_bg, box_border, BW,
                dividers or [], bg,
            )
            _ref(img)
            lbl = ctk.CTkLabel(parent, image=img, text="", fg_color=bg)
            lbl.pack(fill=ctk.X)
            lbl.image = img
            return lbl

        # --- Filename ---
        def _filename(parent):
            lbl_bg = segmented_box(parent)
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            e = ctk.CTkEntry(
                lbl_bg, fg_color=box_bg, text_color="white",
                font=("Segoe UI Variable Display", 12), justify="center",
            )
            e.insert(0, file_name)
            e.configure(state="readonly")
            e.place(x=10, y=0, width=BOX_W - 20, height=BOX_H)
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
                    ctk.CTkLabel(lbl_bg, text=text, text_color="white",
                                 font=("Segoe UI Variable Display", 10), anchor="center"
                                 ).place(x=x, y=2, width=w, height=BOX_H - 4)
            row(_date)

            def _time(parent):
                lbl_bg = segmented_box(parent, [0.5])
                ctk.CTkLabel(lbl_bg, text=str(dt.hour).zfill(2), text_color="white",
                             font=("Segoe UI Variable Display", 10), anchor="center"
                             ).place(x=2, y=2, width=145, height=BOX_H - 4)
                ctk.CTkLabel(lbl_bg, text=dt.strftime("%M"), text_color="white",
                             font=("Segoe UI Variable Display", 10), anchor="center"
                             ).place(x=152, y=2, width=145, height=BOX_H - 4)
            row(_time)

        # Divider
        ctk.CTkFrame(self._content, height=1, fg_color="#2a2a32").pack(fill=ctk.X, pady=8)

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
                gps_row = ctk.CTkFrame(parent, fg_color=bg)
                gps_row.pack(fill=ctk.X, pady=(2, 0))
                ctk.CTkLabel(
                    gps_row, text=exif.gps_string,
                    text_color="#888888",
                    font=("Segoe UI Variable Display", 12), anchor="w",
                ).pack(side=ctk.LEFT, fill=ctk.X, expand=True)
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
            path_row = ctk.CTkFrame(parent, fg_color=bg)
            path_row.pack(fill=ctk.X, pady=(2, 0))

            ctk.CTkLabel(
                path_row, text=file_path, text_color=self._colors.get("accent", "#f08060"),
                             font=("Segoe UI Variable Display", 12),
                anchor="w", justify="left", wraplength=230,
            ).pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            btn_frame = ctk.CTkFrame(path_row, fg_color=bg)
            btn_frame.pack(side=ctk.RIGHT)

            copy_btn = ctk.CTkButton(
                btn_frame, text="⎘", width=24, height=24,
                fg_color=bg, hover_color=self._colors["button_hover"],
                text_color="white",
                command=lambda: self._on_copy_path(file_path) if self._on_copy_path else None,
                font=("Segoe UI Variable Display", 12),
                corner_radius=4,
            )
            copy_btn.pack()
            ToolTip(copy_btn, "Copy path")

            open_btn = ctk.CTkButton(
                btn_frame, text="📂", width=24, height=24,
                fg_color=bg, hover_color=self._colors["button_hover"],
                text_color="white",
                command=lambda: self._on_open_folder(file_path) if self._on_open_folder else None,
                font=("Segoe UI Variable Display", 12),
                corner_radius=4,
            )
            open_btn.pack(pady=(4, 0))
            ToolTip(open_btn, "Open containing folder")
        row(_filepath)