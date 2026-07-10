"""
viewer/ui/dialogs.py
Export progress dialog and Settings dialog.
Now uses customtkinter.
"""

from __future__ import annotations

import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Callable, Optional

from PIL import Image

from ..config import Settings, save_settings


# ---------------------------------------------------------------------------
# Export Progress Dialog
# ---------------------------------------------------------------------------

class ExportProgressDialog:
    """
    Modal progress dialog shown during batch export.
    Runs the actual conversion in a daemon thread.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        colors: dict,
        files: list[str],
        target_dir: str,
        quality: int = 95,
        on_done: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self._parent = parent
        self._colors = colors
        self._files = files
        self._target_dir = target_dir
        self._quality = quality
        self._on_done = on_done

        bg = colors["panel"]
        self._win = ctk.CTkToplevel(parent)
        self._win.title("Exporting…")
        self._win.geometry("420x130")
        self._win.configure(fg_color=bg)
        self._win.transient(parent)
        self._win.grab_set()
        self._win.resizable(False, False)

        # Centre on parent
        self._win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - 210
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - 65
        self._win.geometry(f"+{px}+{py}")

        self._lbl_status = ctk.CTkLabel(
            self._win, text="Preparing…", text_color="white",
            font=("Segoe UI Variable Display", 12),
        )
        self._lbl_status.pack(pady=(16, 4), padx=20, anchor="w")

        self._prog_var = ctk.DoubleVar()
        self._progressbar = ctk.CTkProgressBar(
            self._win, variable=self._prog_var,
            maximum=len(files),
            fg_color="#2a2a32",
            progress_color=colors.get("accent", "#f08060"),
        )
        self._progressbar.pack(fill=ctk.X, padx=20, pady=4)

        self._lbl_count = ctk.CTkLabel(
            self._win, text=f"0 / {len(files)}", text_color="#888888",
            font=("Segoe UI Variable Display", 12),
        )
        self._lbl_count.pack(pady=4)

        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        success = 0
        total = len(self._files)
        for i, path in enumerate(self._files):
            try:
                import os
                self._win.after(
                    0,
                    lambda f=path: self._lbl_status.configure(
                        text=f"Exporting: {os.path.basename(f)}"
                    ),
                )
                img = Image.open(path)
                exif_data   = img.info.get("exif")
                icc_profile = img.info.get("icc_profile")
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                import os as _os
                base = _os.path.splitext(_os.path.basename(path))[0]
                out = _os.path.join(self._target_dir, base + ".jpg")
                kwargs: dict = {"quality": self._quality, "subsampling": 0}
                if exif_data:
                    kwargs["exif"] = exif_data
                if icc_profile:
                    kwargs["icc_profile"] = icc_profile
                img.save(out, "JPEG", **kwargs)
                success += 1
            except Exception:
                pass
            n = i + 1
            self._win.after(0, lambda _n=n: self._prog_var.set(_n))
            self._win.after(0, lambda _n=n: self._lbl_count.configure(text=f"{_n} / {total}"))

        self._win.after(0, self._win.destroy)
        if self._on_done:
            self._win.after(0, lambda: self._on_done(success, total))


# ---------------------------------------------------------------------------
# Settings Dialog
# ---------------------------------------------------------------------------

class SettingsDialog:
    """
    Modal settings window.
    Changes are applied immediately to *settings* and saved on OK.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        colors: dict,
        settings: Settings,
        on_apply: Optional[Callable[[], None]] = None,
    ) -> None:
        self._parent = parent
        self._colors = colors
        self._settings = settings
        self._on_apply = on_apply

        bg = colors["panel"]
        self._win = ctk.CTkToplevel(parent)
        self._win.title("Settings")
        self._win.geometry("480x520")
        self._win.configure(fg_color=bg)
        self._win.transient(parent)
        self._win.grab_set()
        self._win.resizable(False, False)

        # Centre
        self._win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - 240
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - 260
        self._win.geometry(f"+{px}+{py}")

        fg  = "white"
        dim = "#888888"
        hl  = colors.get("accent", "#f08060")
        fnt = ("Segoe UI Variable Display", 12)
        fnt_sm = ("Segoe UI Variable Display", 12)

        def _section(text):
            ctk.CTkLabel(content, text=text, text_color=fg,
                         font=("Segoe UI Variable Display", 12, "bold")).pack(
                anchor="w", pady=(14, 4))
            ctk.CTkFrame(content, height=1, fg_color="#2a2a32").pack(fill=ctk.X)

        def _row(label_text):
            r = ctk.CTkFrame(content, fg_color=bg)
            r.pack(fill=ctk.X, pady=5)
            ctk.CTkLabel(r, text=label_text, text_color=fg, font=fnt, width=22, anchor="w").pack(side=ctk.LEFT)
            return r

        # Scrollable content
        canvas_w = ctk.CTkCanvas(self._win, bg=bg, highlightthickness=0)
        canvas_w.pack(fill=ctk.BOTH, expand=True, padx=20, pady=10)
        content = ctk.CTkFrame(canvas_w, fg_color=bg)
        canvas_w.create_window((0, 0), window=content, anchor="nw")

        # ---- Appearance ----
        _section("Appearance")

        r = _row("Theme")
        self._theme_var = ctk.StringVar(value=settings.theme)
        for val, lbl in [("dark", "Dark"), ("light", "Light")]:
            ctk.CTkRadioButton(
                r, text=lbl, variable=self._theme_var, value=val,
                fg_color=hl, text_color=fg,
                font=fnt_sm,
            ).pack(side=ctk.LEFT, padx=6)

        r = _row("Confirm delete")
        self._confirm_del = ctk.BooleanVar(value=settings.confirm_delete)
        ctk.CTkCheckBox(r, text="", variable=self._confirm_del,
                        fg_color=hl, text_color=fg).pack(side=ctk.LEFT)

        r = _row("Delete to Recycle Bin")
        self._recycle = ctk.BooleanVar(value=settings.delete_to_recycle_bin)
        ctk.CTkCheckBox(r, text="", variable=self._recycle,
                        fg_color=hl, text_color=fg).pack(side=ctk.LEFT)

        # ---- Cache ----
        _section("Performance")

        r = _row("Cache size (MB)")
        self._cache_mb = ctk.IntVar(value=settings.cache_size_mb)
        ctk.CTkSlider(r, from_=50, to=2000, orientation=ctk.HORIZONTAL,
                      variable=self._cache_mb, width=180,
                      fg_color="#3d3d48",
                      button_color=hl, button_hover_color=colors.get("accent_hover", "#ff9a7c"),
                      ).pack(side=ctk.LEFT)
        ctk.CTkLabel(r, textvariable=self._cache_mb, text_color=fg, width=40).pack(side=ctk.LEFT, padx=6)

        r = _row("Thumbnail size (px)")
        self._thumb_size = ctk.IntVar(value=settings.thumbnail_size)
        ctk.CTkSlider(r, from_=48, to=160, orientation=ctk.HORIZONTAL,
                      variable=self._thumb_size, width=180,
                      fg_color="#3d3d48",
                      button_color=hl, button_hover_color=colors.get("accent_hover", "#ff9a7c"),
                      ).pack(side=ctk.LEFT)
        ctk.CTkLabel(r, textvariable=self._thumb_size, text_color=fg, width=40).pack(side=ctk.LEFT, padx=6)

        # ---- Slideshow ----
        _section("Slideshow")

        r = _row("Interval (seconds)")
        self._slideshow_s = ctk.DoubleVar(value=settings.slideshow_interval_s)
        ctk.CTkSlider(r, from_=1, to=30, orientation=ctk.HORIZONTAL,
                      variable=self._slideshow_s, width=180, number_of_steps=58,
                      fg_color="#3d3d48",
                      button_color=hl, button_hover_color=colors.get("accent_hover", "#ff9a7c"),
                      ).pack(side=ctk.LEFT)
        ctk.CTkLabel(r, textvariable=self._slideshow_s, text_color=fg, width=40).pack(side=ctk.LEFT, padx=6)

        # ---- Export ----
        _section("Export")

        r = _row("JPEG quality")
        self._quality = ctk.IntVar(value=settings.export_quality)
        ctk.CTkSlider(r, from_=60, to=100, orientation=ctk.HORIZONTAL,
                      variable=self._quality, width=180, number_of_steps=40,
                      fg_color="#3d3d48",
                      button_color=hl, button_hover_color=colors.get("accent_hover", "#ff9a7c"),
                      ).pack(side=ctk.LEFT)
        ctk.CTkLabel(r, textvariable=self._quality, text_color=fg, width=40).pack(side=ctk.LEFT, padx=6)

        # ---- Buttons ----
        btn_row = ctk.CTkFrame(self._win, fg_color=bg)
        btn_row.pack(fill=ctk.X, padx=20, pady=12)

        ctk.CTkButton(
            btn_row, text="Cancel", command=self._win.destroy,
            fg_color="#2a2a32", hover_color=colors["button_hover"],
            text_color="white",
            font=fnt, corner_radius=6,
        ).pack(side=ctk.RIGHT, padx=6)

        ctk.CTkButton(
            btn_row, text="Save", command=self._save,
            fg_color=colors.get("accent", "#f08060"),
            hover_color=colors.get("accent_hover", "#ff9a7c"),
            text_color="white",
            font=fnt, corner_radius=6,
        ).pack(side=ctk.RIGHT, padx=6)

    def _save(self) -> None:
        s = self._settings
        s.theme                = self._theme_var.get()
        s.confirm_delete       = self._confirm_del.get()
        s.delete_to_recycle_bin = self._recycle.get()
        s.cache_size_mb        = self._cache_mb.get()
        s.thumbnail_size       = self._thumb_size.get()
        s.slideshow_interval_s = self._slideshow_s.get()
        s.export_quality       = self._quality.get()
        save_settings(s)
        if self._on_apply:
            self._on_apply()
        self._win.destroy()