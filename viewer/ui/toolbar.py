"""
viewer/ui/toolbar.py
Top toolbar: Add Files, Add Folder, Export, Copy Image, filename label.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from .widgets import RoundedButton, ToolTip


class Toolbar(tk.Frame):
    """
    The top action bar containing navigation and action buttons plus
    a centred filename label.
    """

    def __init__(
        self,
        parent: tk.Widget,
        colors: dict,
        on_add_files: Optional[Callable] = None,
        on_add_folder: Optional[Callable] = None,
        on_export: Optional[Callable] = None,
        on_copy_image: Optional[Callable] = None,
        on_save_as: Optional[Callable] = None,
    ) -> None:
        bg = colors["panel"]
        super().__init__(parent, bg=bg, height=48)
        self._colors = colors
        self.pack_propagate(False)

        self.grid_columnconfigure(1, weight=1)

        # --- Left button group ---
        left = tk.Frame(self, bg=bg)
        left.grid(row=0, column=0, padx=12, pady=7, sticky="w")

        btn_style = dict(
            height=32,
            radius=7,
            normal_color=colors["button_bg"],
            hover_color=colors["button_hover"],
            fg="white",
            font=("Segoe UI Variable Display", 9),
        )

        self.btn_open = RoundedButton(
            left, text="Add Files", width=86, command=on_add_files, **btn_style
        )
        self.btn_open.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_open, "Open image files  (Ctrl+O)")

        self.btn_folder = RoundedButton(
            left, text="Add Folder", width=90, command=on_add_folder, **btn_style
        )
        self.btn_folder.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_folder, "Open folder  (Ctrl+Shift+O)")

        self.btn_export = RoundedButton(
            left, text="Export JPG", width=86, command=on_export, **btn_style
        )
        self.btn_export.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_export, "Export to JPEG")

        self.btn_copy = RoundedButton(
            left, text="⎘ Copy", width=72, command=on_copy_image, **btn_style
        )
        self.btn_copy.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_copy, "Copy image to clipboard  (Ctrl+C)")

        self.btn_save_as = RoundedButton(
            left, text="Save As", width=72, command=on_save_as, **btn_style
        )
        self.btn_save_as.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_save_as, "Save copy as…  (Ctrl+S)")

        # --- Centre filename label ---
        self.lbl_filename = tk.Label(
            self,
            text="HEIC Photo Viewer",
            bg=bg,
            fg="#cccccc",
            font=("Segoe UI Variable Display", 10),
        )
        self.lbl_filename.grid(row=0, column=1, sticky="nsew")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_title(self, text: str) -> None:
        self.lbl_filename.config(text=text)
