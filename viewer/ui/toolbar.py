"""
viewer/ui/toolbar.py
Top toolbar: Add Files, Add Folder, Export, Copy Image, filename label.
Now uses customtkinter.
"""

from __future__ import annotations

import customtkinter as ctk
from typing import Callable, Optional

from .widgets import ToolTip


class Toolbar(ctk.CTkFrame):
    """
    The top action bar containing navigation and action buttons plus
    a centred filename label.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        colors: dict,
        on_add_files: Optional[Callable] = None,
        on_add_folder: Optional[Callable] = None,
        on_export: Optional[Callable] = None,
        on_copy_image: Optional[Callable] = None,
        on_save_as: Optional[Callable] = None,
    ) -> None:
        bg = colors["panel"]
        super().__init__(parent, fg_color=bg, height=48)
        self._colors = colors
        self.pack_propagate(False)

        self.grid_columnconfigure(1, weight=1)

        # --- Left button group ---
        left = ctk.CTkFrame(self, fg_color=bg)
        left.grid(row=0, column=0, padx=12, pady=7, sticky="w")

        btn_style = dict(
            height=32,
            fg_color=colors["button_bg"],
            hover_color=colors["button_hover"],
            text_color="white",
            font=("Segoe UI Variable Display", 12),
            corner_radius=7,
        )

        self.btn_open = ctk.CTkButton(
            left, text="Add Files", width=86, command=on_add_files, **btn_style
        )
        self.btn_open.pack(side=ctk.LEFT, padx=3)
        ToolTip(self.btn_open, "Open image files  (Ctrl+O)")

        self.btn_folder = ctk.CTkButton(
            left, text="Add Folder", width=90, command=on_add_folder, **btn_style
        )
        self.btn_folder.pack(side=ctk.LEFT, padx=3)
        ToolTip(self.btn_folder, "Open folder  (Ctrl+Shift+O)")

        self.btn_export = ctk.CTkButton(
            left, text="Export JPG", width=86, command=on_export, **btn_style
        )
        self.btn_export.pack(side=ctk.LEFT, padx=3)
        ToolTip(self.btn_export, "Export to JPEG")

        self.btn_copy = ctk.CTkButton(
            left, text="⎘ Copy", width=72, command=on_copy_image, **btn_style
        )
        self.btn_copy.pack(side=ctk.LEFT, padx=3)
        ToolTip(self.btn_copy, "Copy image to clipboard  (Ctrl+C)")

        self.btn_save_as = ctk.CTkButton(
            left, text="Save As", width=72, command=on_save_as, **btn_style
        )
        self.btn_save_as.pack(side=ctk.LEFT, padx=3)
        ToolTip(self.btn_save_as, "Save copy as…  (Ctrl+S)")

        # --- Centre filename label ---
        self.lbl_filename = ctk.CTkLabel(
            self,
            text="HEIC Photo Viewer",
            text_color="#cccccc",
            font=("Segoe UI Variable Display", 12),
        )
        self.lbl_filename.grid(row=0, column=1, sticky="nsew")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_title(self, text: str) -> None:
        self.lbl_filename.configure(text=text)