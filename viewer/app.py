"""
viewer/app.py
HEICViewerApp — main application class.
Wires together all viewer/* modules into a cohesive UI.
"""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional

import pillow_heif

from . import __version__
from .cache import ImageCache
from .config import (Settings, add_recent_file, add_recent_folder,
                     load_settings, save_settings)
from .exif_reader import ExifData
from .formats import FILE_DIALOG_FILTER, FILE_DIALOG_GROUPS, get_supported_files, is_supported
from .image_loader import LoadResult, load_image
from .preloader import Preloader
from .thumbnail_manager import ThumbnailManager
from .ui.canvas_view import ZoomableCanvas
from .ui.dialogs import ExportProgressDialog, SettingsDialog
from .ui.filmstrip import FilmstripPanel
from .ui.sidebar import SidebarPanel
from .ui.statusbar import StatusBar
from .ui.toolbar import Toolbar
from .ui.widgets import RoundedButton, ToolTip
from .windows_integration import (apply_dark_title_bar, copy_image_to_clipboard,
                                   copy_path_to_clipboard, open_containing_folder,
                                   permanent_delete, print_file, register_association,
                                   send_to_recycle_bin, set_dpi_aware)
from . import shortcuts as _shortcuts

logger = logging.getLogger(__name__)

# Register HEIC/HEIF support
pillow_heif.register_heif_opener()


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

DARK_COLORS = {
    "bg":           "#1b1b22",
    "panel":        "#1b1b22",
    "button_bg":    "#2a2a32",
    "button_hover": "#3e3e4a",
    "accent":       "#f08060",
    "accent_hover": "#ff9a7c",
    "viewport":     "#1b1b22",
}

LIGHT_COLORS = {
    "bg":           "#f0f0f4",
    "panel":        "#e8e8f0",
    "button_bg":    "#d4d4e0",
    "button_hover": "#c0c0d0",
    "accent":       "#d05030",
    "accent_hover": "#e06040",
    "viewport":     "#f4f4f8",
}


# ---------------------------------------------------------------------------
# HEICViewerApp
# ---------------------------------------------------------------------------

class HEICViewerApp:
    """Main application controller."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings: Settings = load_settings()
        self._colors = DARK_COLORS if self.settings.theme == "dark" else LIGHT_COLORS

        # Image state
        self._files: list[str] = []
        self._index: int = -1
        self._current_image = None          # PIL Image
        self._current_exif: Optional[ExifData] = None
        self._current_path: str = ""

        # Persistent EXIF cache: stores ExifData read BEFORE ICC conversion
        # (ICC conversion loses the .info dict, so we must capture it first)
        self._exif_cache: dict[str, ExifData] = {}

        # Manual rotation overrides: accumulated CW degrees per file path
        # so rotations survive cache eviction without modifying files on disk
        self._rotation_overrides: dict[str, int] = {}

        # UI state
        self._fullscreen: bool = False
        self._sidebar_visible: bool = False
        self._filmstrip_visible: bool = False
        self._slideshow_active: bool = False
        self._slideshow_id: Optional[str] = None

        # Backend
        self._cache = ImageCache(max_mb=self.settings.cache_size_mb)
        self._preloader = Preloader(self._cache)
        self._thumbs = ThumbnailManager(
            size=self.settings.thumbnail_size, num_workers=2
        )

        self._setup_window()
        self._build_ui()
        self._apply_colors()

        # Start background workers
        self._preloader.start()
        self._thumbs.start(callback=self._on_thumb_ready)
        self.root.after(100, self._poll_thumbs)

        # Bind shortcuts
        _shortcuts.bind_all(self)

        # Windows integration
        register_association()

        # Restore window state
        if self.settings.remember_window_state:
            try:
                self.root.geometry(self.settings.window_geometry)
                if self.settings.window_maximized:
                    self.root.state("zoomed")
            except Exception:
                pass

        # Handle command-line file argument
        if len(sys.argv) > 1:
            path = sys.argv[1]
            if os.path.isfile(path) and is_supported(path):
                self.root.after(150, lambda: self._open_initial(path))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        set_dpi_aware()
        self.root.title("HEIC Photo Viewer")
        self.root.geometry(self.settings.window_geometry)
        self.root.minsize(600, 400)

        # App icon
        try:
            icon_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "assets", "icon.ico"
            )
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        # Dark title bar
        self.root.update()
        try:
            hwnd = self.root.winfo_id()
            parent = __import__("ctypes").windll.user32.GetParent(hwnd)
            apply_dark_title_bar(parent or hwnd)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        c = self._colors
        root = self.root

        root.configure(bg=c["bg"])
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        # --- Toolbar ---
        self.toolbar = Toolbar(
            root, c,
            on_add_files=self.open_files,
            on_add_folder=self.open_folder,
            on_export=self.export_jpg,
            on_copy_image=self.copy_image,
            on_save_as=self.save_as,
        )
        self.toolbar.grid(row=0, column=0, sticky="ew")

        # --- Main display area ---
        self._display = tk.Frame(root, bg=c["bg"])
        self._display.grid(row=1, column=0, sticky="nsew")
        self._display.grid_rowconfigure(0, weight=1)   # canvas row — expand
        self._display.grid_rowconfigure(1, weight=0)   # filmstrip row — fixed height
        self._display.grid_columnconfigure(0, weight=1)

        # Zoomable canvas
        self.canvas_view = ZoomableCanvas(
            self._display,
            bg=c["viewport"],
            on_double_click=self.toggle_fullscreen,
            on_zoom_change=self._on_zoom_changed,
        )
        self.canvas_view.grid(row=0, column=0, sticky="nsew")

        # Sidebar (hidden by default)
        self._sidebar = SidebarPanel(
            self._display, c,
            on_close=self.toggle_sidebar,
            on_copy_path=self._copy_path,
            on_open_folder=lambda p: open_containing_folder(p),
        )

        # Filmstrip (hidden by default)
        self._filmstrip = FilmstripPanel(
            self._display, c,
            on_select=self.load_by_index,
        )

        # Overlay navigation arrows
        self._btn_prev = RoundedButton(
            self.canvas_view.canvas, text="◀", width=36, height=72, radius=6,
            normal_color="#26262e", hover_color="#363642", fg="white",
            command=self.show_prev,
        )
        self._btn_next = RoundedButton(
            self.canvas_view.canvas, text="▶", width=36, height=72, radius=6,
            normal_color="#26262e", hover_color="#363642", fg="white",
            command=self.show_next,
        )

        # Context menu
        self._context_menu = tk.Menu(root, tearoff=0, bg=c["panel"], fg="white",
                                     activebackground=c["button_hover"],
                                     activeforeground="white", bd=0,
                                     font=("Segoe UI Variable Display", 9))
        self._context_menu.add_command(label="Copy Image",          command=self.copy_image)
        self._context_menu.add_command(label="Copy File Path",      command=lambda: self._copy_path(self._current_path))
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Open Containing Folder", command=lambda: open_containing_folder(self._current_path))
        self._context_menu.add_command(label="Print…",              command=self.print_current)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Rotate 90°",          command=self.rotate)
        self._context_menu.add_command(label="Zoom to Fit",         command=self.canvas_view.zoom_to_fit)
        self._context_menu.add_command(label="Actual Size (100%)",  command=self.canvas_view.zoom_to_100)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Image Properties",    command=self.toggle_sidebar)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Move to Recycle Bin", command=self.delete_current)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Settings…",           command=self.open_settings)

        self.canvas_view.canvas.bind("<Button-3>", self._show_context_menu)

        # --- Status bar ---
        self.statusbar = StatusBar(
            root, c,
            on_toggle_info=self.toggle_sidebar,
            on_toggle_filmstrip=self.toggle_filmstrip,
            on_delete=self.delete_current,
            on_rotate=self.rotate,
            on_fit=self.canvas_view.zoom_to_fit,
            on_zoom_in=self.canvas_view.zoom_in,
            on_zoom_out=self.canvas_view.zoom_out,
            on_slider=self._on_slider,
            on_print=self.print_current,
            on_slideshow=self.toggle_slideshow,
            on_open_folder=lambda: open_containing_folder(self._current_path),
        )
        self.statusbar.grid(row=2, column=0, sticky="ew")

    def _apply_colors(self) -> None:
        """Apply current color palette to root and sub-widgets."""
        c = self._colors
        self.root.configure(bg=c["bg"])

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def open_files(self) -> None:
        """Open file dialog for one or more image files."""
        all_types = [FILE_DIALOG_FILTER, ("All Files", "*.*")] + FILE_DIALOG_GROUPS
        paths = filedialog.askopenfilenames(
            title="Open Image(s)",
            filetypes=all_types,
            parent=self.root,
        )
        if not paths:
            return

        if len(paths) == 1:
            # Single file: use folder siblings as context
            path = paths[0]
            folder = os.path.dirname(path)
            all_in_folder = get_supported_files(folder)
            self._files = all_in_folder if all_in_folder else [path]
            try:
                self._index = self._files.index(path)
            except ValueError:
                self._files = [path]
                self._index = 0
            add_recent_file(self.settings, path)
            add_recent_folder(self.settings, folder)
        else:
            self._files = sorted(paths, key=lambda p: os.path.basename(p).lower())
            self._index = 0

        self._load_current(clear_cache=True)

    def open_folder(self) -> None:
        """Open a folder and load all supported images."""
        folder = filedialog.askdirectory(
            title="Select Folder with Images", parent=self.root
        )
        if not folder:
            return
        files = get_supported_files(folder)
        if not files:
            messagebox.showinfo("No Images", "No supported image files found in this folder.")
            return
        self._files = files
        self._index = 0
        add_recent_folder(self.settings, folder)
        self._load_current(clear_cache=True)

    def _open_initial(self, path: str) -> None:
        """Called at startup with a command-line file argument."""
        folder = os.path.dirname(path)
        files = get_supported_files(folder)
        self._files = files if files else [path]
        try:
            self._index = self._files.index(path)
        except ValueError:
            self._index = 0
        self._load_current(clear_cache=False)

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def _load_current(self, clear_cache: bool = False) -> None:
        """Load the image at self._index and update all UI elements."""
        if not self._files or self._index < 0:
            return

        path = self._files[self._index]

        # Kick preloader
        self._preloader.update(self._files, self._index, clear_cache=clear_cache)

        # Update filmstrip
        if self._filmstrip_visible:
            self._filmstrip.set_files(self._files, self._index)
            self._enqueue_thumbs()

        # Try cache first
        cached = self._cache.get(path)
        if cached is not None:
            # Bug 4 fix: use the EXIF we captured at first-load time.
            # Note: the cache already holds the manually-rotated image
            # (rotate() updates the cache), so do NOT re-apply overrides here.
            exif = self._exif_cache.get(path)
            result = LoadResult(image=cached, exif=exif)
            img = cached  # already includes any manual rotation
        else:
            # Load synchronously (preloader may not have caught up yet)
            result = load_image(path)
            if result.ok and result.image:
                # Apply any accumulated manual rotation override before caching
                img = result.image
                extra_degrees = self._rotation_overrides.get(path, 0)
                if extra_degrees:
                    quarter_turns = (extra_degrees // 90) % 4
                    for _ in range(quarter_turns):
                        img = img.rotate(-90, expand=True)
                self._cache.put(path, img)
                if result.exif is not None:
                    self._exif_cache[path] = result.exif
            else:
                img = result.image  # may be None; error handled below

        if not result.ok:
            messagebox.showerror(
                "Cannot Open Image",
                f"Failed to load:\n{os.path.basename(path)}\n\n{result.error}",
            )
            return

        self._current_image = img
        self._current_exif  = result.exif
        self._current_path  = path

        # Update canvas
        self.canvas_view.set_image(img)

        # Update UI labels
        self.toolbar.set_title(os.path.basename(path))
        self._update_metadata_bar()
        self._update_nav_arrows()

        # Update sidebar if visible
        if self._sidebar_visible:
            self._sidebar.populate(path, result.image, result.exif)

        # Filmstrip highlight
        if self._filmstrip_visible:
            self._filmstrip.highlight(self._index)

        # Persist recent
        add_recent_file(self.settings, path)

    def _update_metadata_bar(self) -> None:
        if not self._current_image:
            return
        w, h = self._current_image.size
        try:
            b = os.path.getsize(self._current_path)
            if b < 1024 * 1024:
                sz = f"{b / 1024:.1f} KB"
            else:
                sz = f"{b / (1024 * 1024):.1f} MB"
        except Exception:
            sz = ""
        self.statusbar.update_metadata(f"{w} × {h}  •  {sz}")
        self.statusbar.update_counter(self._index + 1, len(self._files))

    def _update_nav_arrows(self) -> None:
        if len(self._files) > 1:
            self._btn_prev.place(relx=0.01, rely=0.5, anchor=tk.W)
            self._btn_next.place(relx=0.99, rely=0.5, anchor=tk.E)
        else:
            self._btn_prev.place_forget()
            self._btn_next.place_forget()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_next(self, event=None) -> None:
        if len(self._files) > 1:
            self.load_by_index((self._index + 1) % len(self._files))

    def show_prev(self, event=None) -> None:
        if len(self._files) > 1:
            self.load_by_index((self._index - 1) % len(self._files))

    def show_first(self) -> None:
        if self._files:
            self.load_by_index(0)

    def show_last(self) -> None:
        if self._files:
            self.load_by_index(len(self._files) - 1)

    def load_by_index(self, idx: int) -> None:
        if not self._files or idx < 0 or idx >= len(self._files):
            return
        self._index = idx
        self._load_current()

    # ------------------------------------------------------------------
    # Image actions
    # ------------------------------------------------------------------

    def rotate(self) -> None:
        if not self._current_image or not self._current_path:
            return
        # Bug 7 fix: track the manual rotation in _rotation_overrides instead
        # of baking it into the cache. This way if the cached image is evicted
        # and reloaded from disk, we re-apply the override on top of EXIF
        # correction rather than double-rotating.
        self._current_image = self._current_image.rotate(-90, expand=True)
        prev = self._rotation_overrides.get(self._current_path, 0)
        self._rotation_overrides[self._current_path] = (prev + 90) % 360
        # Update the cache with the newly-rotated image so the next cache hit
        # returns the right view (we also update _exif_cache to avoid a
        # spurious re-rotation on the next load)
        self._cache.put(self._current_path, self._current_image)
        self.canvas_view.set_image(self._current_image)
        if self._sidebar_visible:
            self._sidebar.populate(self._current_path, self._current_image, self._current_exif)

    def copy_image(self) -> None:
        if not self._current_image:
            return
        ok = copy_image_to_clipboard(self._current_image)
        if not ok:
            messagebox.showerror("Copy Failed", "Could not copy image to clipboard.")

    def save_as(self) -> None:
        if not self._current_image or not self._current_path:
            return
        base = os.path.splitext(os.path.basename(self._current_path))[0]
        path = filedialog.asksaveasfilename(
            title="Save Image As",
            initialfile=base + ".jpg",
            defaultextension=".jpg",
            filetypes=[
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("WebP", "*.webp"),
                ("All Files", "*.*"),
            ],
            parent=self.root,
        )
        if not path:
            return
        try:
            img = self._current_image
            if img.mode in ("RGBA", "P") and path.lower().endswith((".jpg", ".jpeg")):
                img = img.convert("RGB")
            img.save(path)
            messagebox.showinfo("Saved", f"Image saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))

    def delete_current(self) -> None:
        if not self._current_path or not self._files:
            return

        if self.settings.confirm_delete:
            name = os.path.basename(self._current_path)
            action = "move to Recycle Bin" if self.settings.delete_to_recycle_bin else "permanently delete"
            if not messagebox.askyesno("Delete", f"Are you sure you want to {action}:\n{name}?"):
                return

        path = self._current_path
        self._cache.remove(path)
        self._files.pop(self._index)

        if self.settings.delete_to_recycle_bin:
            ok = send_to_recycle_bin(path)
        else:
            ok = permanent_delete(path)

        if not ok:
            messagebox.showerror("Delete Failed", f"Could not delete:\n{path}")
            self._files.insert(self._index, path)
            return

        if self._files:
            self._index = min(self._index, len(self._files) - 1)
            self._load_current()
        else:
            self._index = -1
            self._current_image = None
            self._current_path = ""
            self.canvas_view.clear()
            self.toolbar.set_title("HEIC Photo Viewer")
            self.statusbar.update_metadata("")
            self.statusbar.update_counter(0, 0)
            self._btn_prev.place_forget()
            self._btn_next.place_forget()
            if self._sidebar_visible:
                self._sidebar.populate("", None, None)
            if self._filmstrip_visible:
                self._filmstrip.clear()

    def print_current(self) -> None:
        if self._current_path:
            print_file(self._current_path)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_jpg(self) -> None:
        if not self._files:
            messagebox.showinfo("Export", "No images loaded.")
            return

        choice = messagebox.askyesnocancel(
            "Export to JPG",
            "Export options:\n\n"
            "Yes  → Export all loaded images\n"
            "No   → Export current image only\n"
            "Cancel → Abort",
        )
        if choice is None:
            return
        if choice:
            target = filedialog.askdirectory(title="Choose Export Folder", parent=self.root)
            if not target:
                return
            ExportProgressDialog(
                self.root, self._colors, self._files, target,
                quality=self.settings.export_quality,
                on_done=lambda ok, tot: messagebox.showinfo(
                    "Export Complete", f"Exported {ok} of {tot} images to:\n{target}"
                ),
            )
        else:
            self._export_single()

    def _export_single(self) -> None:
        if not self._current_image or not self._current_path:
            return
        base = os.path.splitext(os.path.basename(self._current_path))[0]
        path = filedialog.asksaveasfilename(
            title="Export Image as JPEG",
            initialfile=base + ".jpg",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg *.jpeg")],
            parent=self.root,
        )
        if not path:
            return
        try:
            from PIL import Image as _Image
            img = self._current_image.copy()
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            kwargs: dict = {"quality": self.settings.export_quality, "subsampling": 0}
            # Preserve EXIF / ICC if available from file
            try:
                src = _Image.open(self._current_path)
                if "exif" in src.info:
                    kwargs["exif"] = src.info["exif"]
                if "icc_profile" in src.info:
                    kwargs["icc_profile"] = src.info["icc_profile"]
            except Exception:
                pass
            img.save(path, "JPEG", **kwargs)
            messagebox.showinfo("Exported", f"Image saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    # ------------------------------------------------------------------
    # View toggles
    # ------------------------------------------------------------------

    def toggle_fullscreen(self, event=None) -> None:
        self._fullscreen = not self._fullscreen
        self.root.attributes("-fullscreen", self._fullscreen)
        if self._fullscreen:
            self.toolbar.grid_remove()
            self.statusbar.grid_remove()
            if self._sidebar_visible:
                self._sidebar.grid_remove()
        else:
            self.toolbar.grid()
            self.statusbar.grid()
            if self._sidebar_visible:
                self._sidebar.grid(row=0, column=1, sticky="ns",
                                   in_=self._display)  # Bug 2 fix: must use in_=
            self.root.focus_set()

    def exit_fullscreen(self, event=None) -> None:
        if self._fullscreen:
            self.toggle_fullscreen()

    def toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        if self._sidebar_visible:
            self._sidebar.grid(row=0, column=1, sticky="ns",
                                in_=self._display)
            self._sidebar.populate(
                self._current_path, self._current_image, self._current_exif
            )
        else:
            self._sidebar.grid_forget()
        self.statusbar.set_info_active(self._sidebar_visible)
        # Redraw to use new canvas width
        self.root.update_idletasks()
        if self._current_image:
            self.canvas_view.zoom_to_fit()

    def toggle_filmstrip(self) -> None:
        self._filmstrip_visible = not self._filmstrip_visible
        if self._filmstrip_visible:
            self._filmstrip.grid(row=1, column=0, sticky="ew",
                                  in_=self._display, columnspan=2)
            if self._files:
                self._filmstrip.set_files(self._files, self._index)
                self._enqueue_thumbs()
        else:
            self._filmstrip.grid_forget()
            self._thumbs.clear_queue()
        self.statusbar.set_filmstrip_active(self._filmstrip_visible)

    def toggle_slideshow(self) -> None:
        self._slideshow_active = not self._slideshow_active
        self.statusbar.set_slideshow_active(self._slideshow_active)
        if self._slideshow_active:
            self._advance_slideshow()
        else:
            if self._slideshow_id:
                self.root.after_cancel(self._slideshow_id)
                self._slideshow_id = None

    def _advance_slideshow(self) -> None:
        # Bug 6 fix: don't loop if only one image is loaded
        if not self._slideshow_active or len(self._files) < 2:
            if self._slideshow_active and len(self._files) < 2:
                self.toggle_slideshow()  # auto-stop
            return
        self.show_next()
        delay_ms = int(self.settings.slideshow_interval_s * 1000)
        self._slideshow_id = self.root.after(delay_ms, self._advance_slideshow)

    # ------------------------------------------------------------------
    # Clipboard & path
    # ------------------------------------------------------------------

    def _copy_path(self, path: str) -> None:
        copy_path_to_clipboard(path, self.root)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def open_settings(self) -> None:
        SettingsDialog(
            self.root, self._colors, self.settings,
            on_apply=self._apply_settings,
        )

    def _apply_settings(self) -> None:
        self._cache.resize(self.settings.cache_size_mb)

    # ------------------------------------------------------------------
    # Zoom/slider callbacks
    # ------------------------------------------------------------------

    def _on_zoom_changed(self, zoom: float) -> None:
        self.statusbar.update_zoom(zoom)

    def _on_slider(self, val: str) -> None:
        if not self._current_image:
            return
        pct = float(val)
        self.canvas_view.set_zoom(pct / 100.0)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, event: tk.Event) -> None:
        if not self._current_image:
            return
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    # ------------------------------------------------------------------
    # Thumbnail pipeline
    # ------------------------------------------------------------------

    def _enqueue_thumbs(self) -> None:
        self._thumbs.clear_queue()
        for i, path in enumerate(self._files):
            self._thumbs.enqueue(i, path)

    def _on_thumb_ready(self, idx: int, img) -> None:
        """Deliver thumbnail to filmstrip (called from main thread via poll)."""
        if self._filmstrip_visible:
            self._filmstrip.on_thumb_ready(idx, img)

    def _poll_thumbs(self) -> None:
        self._thumbs.poll(max_per_call=5)
        self.root.after(80, self._poll_thumbs)

    # ------------------------------------------------------------------
    # Close / cleanup
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        # Stop slideshow
        if self._slideshow_id:
            self.root.after_cancel(self._slideshow_id)

        # Persist window state
        if self.settings.remember_window_state:
            self.settings.window_maximized = self.root.state() == "zoomed"
            if not self.settings.window_maximized:
                self.settings.window_geometry = self.root.geometry()
        save_settings(self.settings)

        self._preloader.stop()
        self._thumbs.stop()
        self.root.destroy()
