"""
viewer/ui/dialogs.py
Export progress dialog and Settings dialog.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, ttk
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
        parent: tk.Widget,
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
        self._win = tk.Toplevel(parent)
        self._win.title("Exporting…")
        self._win.geometry("420x130")
        self._win.configure(bg=bg)
        self._win.transient(parent)
        self._win.grab_set()
        self._win.resizable(False, False)

        # Centre on parent
        self._win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - 210
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - 65
        self._win.geometry(f"+{px}+{py}")

        self._lbl_status = tk.Label(
            self._win, text="Preparing…", bg=bg, fg="white",
            font=("Segoe UI Variable Display", 10),
        )
        self._lbl_status.pack(pady=(16, 4), padx=20, anchor="w")

        style = ttk.Style(self._win)
        style.theme_use("default")
        style.configure(
            "Export.TProgressbar",
            thickness=12,
            background=colors.get("accent", "#f08060"),
            troughcolor="#2a2a32",
        )
        self._prog_var = tk.DoubleVar()
        self._progressbar = ttk.Progressbar(
            self._win, variable=self._prog_var,
            maximum=len(files), style="Export.TProgressbar",
        )
        self._progressbar.pack(fill=tk.X, padx=20, pady=4)

        self._lbl_count = tk.Label(
            self._win, text=f"0 / {len(files)}", bg=bg, fg="#888888",
            font=("Segoe UI Variable Display", 9),
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
                    lambda f=path: self._lbl_status.config(
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
            self._win.after(0, lambda _n=n: self._lbl_count.config(text=f"{_n} / {total}"))

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
        parent: tk.Widget,
        colors: dict,
        settings: Settings,
        on_apply: Optional[Callable[[], None]] = None,
    ) -> None:
        self._parent = parent
        self._colors = colors
        self._settings = settings
        self._on_apply = on_apply

        bg = colors["panel"]
        self._win = tk.Toplevel(parent)
        self._win.title("Settings")
        self._win.geometry("480x520")
        self._win.configure(bg=bg)
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
        fnt = ("Segoe UI Variable Display", 10)
        fnt_sm = ("Segoe UI Variable Display", 9)

        def _section(text):
            tk.Label(content, text=text, bg=bg, fg=fg,
                     font=("Segoe UI Variable Display", 11, "bold")).pack(
                anchor="w", pady=(14, 4))
            tk.Frame(content, height=1, bg="#2a2a32").pack(fill=tk.X)

        def _row(label_text):
            r = tk.Frame(content, bg=bg)
            r.pack(fill=tk.X, pady=5)
            tk.Label(r, text=label_text, bg=bg, fg=fg, font=fnt, width=22, anchor="w").pack(side=tk.LEFT)
            return r

        # Scrollable content
        canvas_w = tk.Canvas(self._win, bg=bg, highlightthickness=0)
        canvas_w.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        content = tk.Frame(canvas_w, bg=bg)
        canvas_w.create_window((0, 0), window=content, anchor="nw")

        # ---- Appearance ----
        _section("Appearance")

        r = _row("Theme")
        self._theme_var = tk.StringVar(value=settings.theme)
        for val, lbl in [("dark", "Dark"), ("light", "Light")]:
            tk.Radiobutton(
                r, text=lbl, variable=self._theme_var, value=val,
                bg=bg, fg=fg, selectcolor="#2a2a32",
                activebackground=bg, font=fnt_sm,
            ).pack(side=tk.LEFT, padx=6)

        r = _row("Confirm delete")
        self._confirm_del = tk.BooleanVar(value=settings.confirm_delete)
        tk.Checkbutton(r, variable=self._confirm_del, bg=bg, fg=fg,
                       selectcolor="#2a2a32", activebackground=bg).pack(side=tk.LEFT)

        r = _row("Delete to Recycle Bin")
        self._recycle = tk.BooleanVar(value=settings.delete_to_recycle_bin)
        tk.Checkbutton(r, variable=self._recycle, bg=bg, fg=fg,
                       selectcolor="#2a2a32", activebackground=bg).pack(side=tk.LEFT)

        # ---- Cache ----
        _section("Performance")

        r = _row("Cache size (MB)")
        self._cache_mb = tk.IntVar(value=settings.cache_size_mb)
        tk.Scale(r, from_=50, to=2000, orient=tk.HORIZONTAL,
                 variable=self._cache_mb, length=180,
                 bg=bg, fg=fg, highlightthickness=0,
                 troughcolor="#3d3d48", showvalue=1,
                 font=fnt_sm).pack(side=tk.LEFT)

        r = _row("Thumbnail size (px)")
        self._thumb_size = tk.IntVar(value=settings.thumbnail_size)
        tk.Scale(r, from_=48, to=160, orient=tk.HORIZONTAL,
                 variable=self._thumb_size, length=180,
                 bg=bg, fg=fg, highlightthickness=0,
                 troughcolor="#3d3d48", showvalue=1,
                 font=fnt_sm).pack(side=tk.LEFT)

        # ---- Slideshow ----
        _section("Slideshow")

        r = _row("Interval (seconds)")
        self._slideshow_s = tk.DoubleVar(value=settings.slideshow_interval_s)
        tk.Scale(r, from_=1, to=30, orient=tk.HORIZONTAL,
                 variable=self._slideshow_s, length=180, resolution=0.5,
                 bg=bg, fg=fg, highlightthickness=0,
                 troughcolor="#3d3d48", showvalue=1,
                 font=fnt_sm).pack(side=tk.LEFT)

        # ---- Export ----
        _section("Export")

        r = _row("JPEG quality")
        self._quality = tk.IntVar(value=settings.export_quality)
        tk.Scale(r, from_=60, to=100, orient=tk.HORIZONTAL,
                 variable=self._quality, length=180,
                 bg=bg, fg=fg, highlightthickness=0,
                 troughcolor="#3d3d48", showvalue=1,
                 font=fnt_sm).pack(side=tk.LEFT)

        # ---- Buttons ----
        btn_row = tk.Frame(self._win, bg=bg)
        btn_row.pack(fill=tk.X, padx=20, pady=12)

        tk.Button(
            btn_row, text="Cancel", command=self._win.destroy,
            bg="#2a2a32", fg="white", relief="flat",
            font=fnt, padx=12, pady=4, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=6)

        tk.Button(
            btn_row, text="Save", command=self._save,
            bg=colors.get("accent", "#f08060"), fg="white", relief="flat",
            font=fnt, padx=12, pady=4, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=6)

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
