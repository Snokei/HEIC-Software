"""
viewer/shortcuts.py
All keyboard bindings for HEICViewerApp.
Centralised so every shortcut is visible in one place.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import HEICViewerApp


def bind_all(app: "HEICViewerApp") -> None:
    """Attach every keyboard shortcut to the root window."""
    root = app.root

    # --- Navigation ---
    root.bind("<Right>",       lambda e: app.show_next())
    root.bind("<Left>",        lambda e: app.show_prev())
    root.bind("<space>",       lambda e: app.show_next())
    root.bind("<BackSpace>",   lambda e: app.show_prev())
    root.bind("<Home>",        lambda e: app.show_first())
    root.bind("<End>",         lambda e: app.show_last())

    # --- Zoom ---
    root.bind("<Up>",          lambda e: app.canvas_view.zoom_in())
    root.bind("<Down>",        lambda e: app.canvas_view.zoom_out())
    root.bind("f",             lambda e: app.canvas_view.zoom_to_fit())
    root.bind("F",             lambda e: app.canvas_view.zoom_to_fit())
    root.bind("1",             lambda e: app.canvas_view.zoom_to_100())

    # --- File ---
    root.bind("<Control-o>",         lambda e: app.open_files())
    root.bind("<Control-O>",         lambda e: app.open_files())
    root.bind("<Control-Shift-O>",   lambda e: app.open_folder())
    root.bind("<Control-s>",         lambda e: app.save_as())
    root.bind("<Control-S>",         lambda e: app.save_as())

    # --- Clipboard ---
    root.bind("<Control-c>",         lambda e: app.copy_image())
    root.bind("<Control-C>",         lambda e: app.copy_image())

    # --- Image actions ---
    root.bind("r",             lambda e: app.rotate())
    root.bind("R",             lambda e: app.rotate())
    root.bind("<Delete>",      lambda e: app.delete_current())

    # --- View toggles ---
    root.bind("<F11>",         lambda e: app.toggle_fullscreen())
    root.bind("<Escape>",      lambda e: app.exit_fullscreen())
    root.bind("i",             lambda e: app.toggle_sidebar())
    root.bind("I",             lambda e: app.toggle_sidebar())
    # "f" is zoom_to_fit above; filmstrip uses separate key
    root.bind("<Control-f>",   lambda e: app.toggle_filmstrip())
    root.bind("<Control-F>",   lambda e: app.toggle_filmstrip())

    # --- Slideshow ---
    root.bind("s",             lambda e: app.toggle_slideshow())
    root.bind("S",             lambda e: app.toggle_slideshow())

    # --- Print ---
    root.bind("<Control-p>",   lambda e: app.print_current())
    root.bind("<Control-P>",   lambda e: app.print_current())

    # --- Settings ---
    root.bind("<Control-comma>", lambda e: app.open_settings())
