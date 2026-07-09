"""
viewer/windows_integration.py
Native Windows operations: clipboard, Recycle Bin, Explorer integration.
All functions fail gracefully with logged warnings — never crash the app.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

def copy_image_to_clipboard(pil_image) -> bool:
    """
    Copy a PIL Image to the Windows clipboard as a DIB (device-independent bitmap).
    Returns True on success.
    """
    try:
        import ctypes
        import io
        import struct

        # Convert to BMP in memory
        buf = io.BytesIO()
        rgb_image = pil_image.convert("RGB")
        rgb_image.save(buf, format="BMP")
        bmp_data = buf.getvalue()

        # BMP file header is 14 bytes; strip it to get DIB
        dib_data = bmp_data[14:]

        CF_DIB = 8
        GMEM_MOVEABLE = 0x0002

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        if not user32.OpenClipboard(None):
            return False

        user32.EmptyClipboard()
        hglob = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib_data))
        ptr = kernel32.GlobalLock(hglob)
        ctypes.memmove(ptr, dib_data, len(dib_data))
        kernel32.GlobalUnlock(hglob)
        user32.SetClipboardData(CF_DIB, hglob)
        user32.CloseClipboard()
        return True
    except Exception as exc:
        logger.warning("copy_image_to_clipboard failed: %s", exc)
        return False


def copy_path_to_clipboard(path: str, root_widget=None) -> bool:
    """Copy a file path string to the clipboard. Uses Tk as fallback."""
    try:
        import ctypes
        text = path
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        encoded = (text + "\x00").encode("utf-16-le")
        if not user32.OpenClipboard(None):
            raise RuntimeError("OpenClipboard failed")
        user32.EmptyClipboard()
        hglob = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        ptr = kernel32.GlobalLock(hglob)
        ctypes.memmove(ptr, encoded, len(encoded))
        kernel32.GlobalUnlock(hglob)
        user32.SetClipboardData(CF_UNICODETEXT, hglob)
        user32.CloseClipboard()
        return True
    except Exception:
        # Fallback: use Tk clipboard
        if root_widget is not None:
            try:
                root_widget.clipboard_clear()
                root_widget.clipboard_append(path)
                return True
            except Exception:
                pass
        return False


# ---------------------------------------------------------------------------
# Recycle Bin / Delete
# ---------------------------------------------------------------------------

def send_to_recycle_bin(path: str) -> bool:
    """
    Move *path* to the Windows Recycle Bin.
    Falls back to permanent delete if send2trash is unavailable.
    Returns True on success.
    """
    try:
        import send2trash  # type: ignore
        send2trash.send2trash(path)
        return True
    except ImportError:
        logger.warning("send2trash not installed; falling back to permanent delete.")
        return _permanent_delete(path)
    except Exception as exc:
        logger.error("Recycle Bin error for %s: %s", path, exc)
        return False


def permanent_delete(path: str) -> bool:
    return _permanent_delete(path)


def _permanent_delete(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except Exception as exc:
        logger.error("Delete failed for %s: %s", path, exc)
        return False


# ---------------------------------------------------------------------------
# Explorer integration
# ---------------------------------------------------------------------------

def open_containing_folder(path: str) -> bool:
    """Open Windows Explorer, selecting the given file."""
    try:
        subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])
        return True
    except Exception as exc:
        logger.warning("open_containing_folder failed: %s", exc)
        return False


def open_with_default_app(path: str) -> bool:
    """Open *path* with its default associated application."""
    try:
        os.startfile(path)
        return True
    except Exception as exc:
        logger.warning("open_with_default_app failed: %s", exc)
        return False


def print_file(path: str) -> bool:
    """Send *path* to the Windows print wizard."""
    try:
        os.startfile(path, "print")
        return True
    except Exception as exc:
        logger.warning("print_file failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# System theme detection
# ---------------------------------------------------------------------------

def get_system_theme() -> str:
    """
    Return 'dark' or 'light' based on the Windows system theme.
    Reads HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize.
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"


# ---------------------------------------------------------------------------
# DWM dark title bar
# ---------------------------------------------------------------------------

def apply_dark_title_bar(hwnd: int) -> None:
    """Apply dark title bar to the given window handle via DWM."""
    try:
        import ctypes
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception as exc:
        logger.debug("apply_dark_title_bar failed: %s", exc)


def set_dpi_aware() -> None:
    """Enable per-monitor DPI awareness for the process."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor v2
    except Exception:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# File association (moved from main file)
# ---------------------------------------------------------------------------

def register_association(exe_path: Optional[str] = None) -> None:
    """Register .heic/.heif file associations silently (no-op on failure)."""
    if exe_path is None:
        exe_path = os.path.abspath(sys.executable)
    if os.path.basename(exe_path).lower() in ("python.exe", "pythonw.exe"):
        return  # Don't register for dev installs

    try:
        import ctypes
        import winreg

        assoc_name = "HEICViewer.AssocFile"

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{assoc_name}") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "HEIC Image File")

        cmd_path = rf"Software\Classes\{assoc_name}\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')

        for ext in (".heic", ".heif"):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, assoc_name)

        app_path = rf"Software\Classes\Applications\heic_viewer.exe\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')

        uninstall = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HEICViewer"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall) as key:
            winreg.SetValue(key, "DisplayName",    winreg.REG_SZ, "HEIC Photo Viewer")
            winreg.SetValue(key, "UninstallString", winreg.REG_SZ, f'"{exe_path}" --uninstall')
            winreg.SetValue(key, "DisplayVersion", winreg.REG_SZ, "2.0.0")
            winreg.SetValue(key, "Publisher",      winreg.REG_SZ, "HEIC Software")
            winreg.SetValue(key, "DisplayIcon",    winreg.REG_SZ, exe_path)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair",  0, winreg.REG_DWORD, 1)

        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception as exc:
        logger.debug("register_association failed: %s", exc)


def unregister_association() -> None:
    """Remove all HEIC file associations created by this app."""
    try:
        import ctypes
        import winreg

        def _del(root, subkey):
            try:
                key = winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS)
                while True:
                    try:
                        sub = winreg.EnumKey(key, 0)
                        _del(key, sub)
                    except OSError:
                        break
                winreg.CloseKey(key)
                winreg.DeleteKey(root, subkey)
            except FileNotFoundError:
                pass

        _del(winreg.HKEY_CURRENT_USER, r"Software\Classes\HEICViewer.AssocFile")
        _del(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\heic_viewer.exe")

        for ext in (r"Software\Classes\.heic", r"Software\Classes\.heif"):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ext, 0, winreg.KEY_ALL_ACCESS) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val == "HEICViewer.AssocFile":
                        winreg.DeleteValue(key, "")
            except FileNotFoundError:
                pass

        _del(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HEICViewer")
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception as exc:
        logger.debug("unregister_association failed: %s", exc)
