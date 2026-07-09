"""
heic_viewer.py — Entry point for HEIC Photo Viewer.

This thin launcher handles:
  1. The --uninstall command-line flag (before any window is created)
  2. DPI awareness (before Tk root is instantiated)
  3. Launching HEICViewerApp
"""

import sys
import os

# Ensure the package directory is resolvable regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Handle --uninstall before importing anything heavy (Bug 10 fix)
if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
    from viewer.windows_integration import unregister_association
    unregister_association()
    sys.exit(0)

import tkinter as tk
from viewer.app import HEICViewerApp

if __name__ == "__main__":
    root = tk.Tk()
    app = HEICViewerApp(root)
    root.mainloop()