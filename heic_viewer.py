import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageCms, ImageFilter, ImageDraw
import pillow_heif
import io
import os
import sys
import datetime
import threading
import queue
from collections import OrderedDict

def get_file_size_str(file_path):
    try:
        size_bytes = os.path.getsize(file_path)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    except Exception:
        return ""

def make_rounded_rect_image(width, height, radius, bg_color, parent_bg):
    img = Image.new("RGBA", (width, height), parent_bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=bg_color)
    return ImageTk.PhotoImage(img)

def make_rounded_segmented_image(width, height, radius, fill_color, border_color, border_width, dividers, parent_bg):
    img = Image.new("RGBA", (width, height), parent_bg)
    draw = ImageDraw.Draw(img)
    # Draw rounded rect
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=fill_color,
        outline=border_color,
        width=border_width
    )
    # Draw vertical divider lines
    for d in dividers:
        x = int(width * d)
        draw.line((x, border_width, x, height - 1 - border_width), fill=border_color, width=border_width)
    return ImageTk.PhotoImage(img)

# Custom Tooltip class
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        
    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        # Calculate cursor offset position below button
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 50
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            tw, 
            text=self.text, 
            justify=tk.LEFT,
            background="#252528", 
            foreground="white", 
            relief=tk.FLAT, 
            font=("Segoe UI Variable Display", 9),
            padx=8,
            pady=4
        )
        label.pack()
        
    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

# Custom Rounded Button class using PIL rounded images with parent bg mapping
class RoundedButton(tk.Button):
    def __init__(self, parent, text, width, height, radius, normal_color, hover_color, fg, hover_fg=None, command=None, font=("Segoe UI Variable Display", 9)):
        self.width = width
        self.height = height
        self.radius = radius
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.fg = fg
        self.hover_fg = hover_fg or fg
        
        # Get parent background color
        parent_bg = parent.cget("bg")
        
        # Generate images with parent background for seamless corner blending
        self.img_normal = make_rounded_rect_image(width, height, radius, normal_color, parent_bg)
        self.img_hover = make_rounded_rect_image(width, height, radius, hover_color, parent_bg)
        
        super().__init__(
            parent,
            text=text,
            image=self.img_normal,
            compound="center",
            fg=self.fg,
            activeforeground=self.hover_fg,
            bg=parent_bg,
            activebackground=parent_bg,
            relief="flat",
            bd=0,
            highlightthickness=0, # Clear selection highlight
            command=command,
            font=font,
            cursor="hand2"
        )
        
        # Bind hover events
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        
    def _on_enter(self, event):
        self.config(image=self.img_hover, fg=self.hover_fg)
        
    def _on_leave(self, event):
        self.config(image=self.img_normal, fg=self.fg)

# Handlers for uninstall command line flag before window creation
def check_uninstall_args():
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        unregister_association_self()
        sys.exit(0)

def unregister_association_self():
    import winreg
    
    def delete_key_recursive(root_key, subkey):
        try:
            key = winreg.OpenKey(root_key, subkey, 0, winreg.KEY_ALL_ACCESS)
            while True:
                try:
                    sub = winreg.EnumKey(key, 0)
                    delete_key_recursive(key, sub)
                except OSError:
                    break
            winreg.CloseKey(key)
            winreg.DeleteKey(root_key, subkey)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error deleting key {subkey}: {e}")

    try:
        # Delete associations
        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\HEICViewer.AssocFile")
        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Classes\Applications\heic_viewer.exe")
        
        for ext in (r"Software\Classes\.heic", r"Software\Classes\.heif"):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ext, 0, winreg.KEY_ALL_ACCESS) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val == "HEICViewer.AssocFile":
                        winreg.DeleteValue(key, "")
            except FileNotFoundError:
                pass
                
        # Delete Uninstall registration
        delete_key_recursive(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HEICViewer")
        
        # Notify shell
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        print("Unregistration complete.")
    except Exception as e:
        print(f"Failed to unregister: {e}")

# Call immediately upon execution
check_uninstall_args()

# Set DPI awareness for Windows to unblur the Tkinter window
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Register the HEIC plugin so Pillow can read .heic files
pillow_heif.register_heif_opener()

class HEICViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("") # Empty title to clear native text on left
        self.root.geometry("1100x750") # Slightly wider by default to fit sidebar drawer
        
        # Glassmorphism Color Palette (Borderless rounded version)
        self.clr_bg = "#1b1b22"            # Unified glass base dark (matches panel)
        self.clr_panel = "#1b1b22"         # Frosted glass panel surface
        self.clr_button_bg = "#2a2a32"     # Dark grey button background (from screenshot)
        self.clr_button_hover = "#3e3e4a"  # Lighter hover background (from screenshot)
        self.clr_accent = "#f08060"        # Glowing coral accent
        self.clr_accent_hover = "#ff9a7c"  # Coral hover
        self.clr_viewport = "#1b1b22"      # Glassmorphic unified dark viewport background (matches clr_bg!)
        
        self.root.configure(bg=self.clr_bg)
        
        # Title bar simulation and top action toolbar (Borders removed)
        self.top_frame = tk.Frame(
            root, 
            bg=self.clr_panel, 
            height=45
        )
        self.top_frame.pack(side=tk.TOP, fill=tk.X)
        self.top_frame.grid_columnconfigure(1, weight=1) # Center spacing
        
        # Left Actions Container (Within Top Frame)
        self.left_actions = tk.Frame(self.top_frame, bg=self.clr_panel)
        self.left_actions.grid(row=0, column=0, padx=12, pady=6, sticky="w")
        
        # EXACTLY 1 BUTTON ON TOP WITH PIXEL-PERFECT DARK GREY FLUID DESIGN
        button_font = ("Segoe UI Variable Display", 9)
        
        # 1. Add Files Button
        self.btn_open = RoundedButton(
            self.left_actions,
            text="Add Files",
            width=86,
            height=32,
            radius=6,
            normal_color=self.clr_button_bg,
            hover_color=self.clr_button_hover,
            fg="white",
            command=self.open_heic,
            font=button_font
        )
        self.btn_open.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_open, "Open HEIC photo files (Ctrl+O)")
        
        # 2. Add Folder Button
        self.btn_open_folder = RoundedButton(
            self.left_actions,
            text="Add Folder",
            width=90,
            height=32,
            radius=6,
            normal_color=self.clr_button_bg,
            hover_color=self.clr_button_hover,
            fg="white",
            command=self.open_folder,
            font=button_font
        )
        self.btn_open_folder.pack(side=tk.LEFT, padx=4)
        ToolTip(self.btn_open_folder, "Open folder containing HEIC photos")
        
        # Centered Filename Label
        self.lbl_filename = tk.Label(
            self.top_frame, 
            text="", 
            bg=self.clr_panel, 
            fg="#cccccc", 
            font=("Segoe UI Variable Display", 10)
        )
        self.lbl_filename.grid(row=0, column=1, sticky="nsew")
        
        # Image Display Area (Center Viewport)
        self.display_frame = tk.Frame(root, bg=self.clr_viewport)
        self.display_frame.pack(fill=tk.BOTH, expand=True)
        
        self.display_frame.grid_rowconfigure(0, weight=1)
        self.display_frame.grid_columnconfigure(0, weight=1)
        self.display_frame.grid_columnconfigure(1, weight=0) # Sidebar column
        
        # Canvas Container Frame (so we can grid it alongside scrollbars)
        self.canvas_frame = tk.Frame(self.display_frame, bg=self.clr_viewport)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollbars
        self.v_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.h_scrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        
        self.canvas = tk.Canvas(
            self.canvas_frame, 
            bg=self.clr_viewport, 
            highlightthickness=0,
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set
        )
        
        self.v_scrollbar.config(command=self.canvas.yview)
        self.h_scrollbar.config(command=self.canvas.xview)
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # State variables
        self.original_image = None
        self.zoom_scale = 1.0
        self.view_mode = "fit"
        self.canvas_width = 0
        self.canvas_height = 0
        self.image_container = None
        
        # Folder navigation variables
        self.folder_files = []
        self.current_index = -1
        self.is_fullscreen = False
        self.slideshow_active = False
        self.sidebar_visible = False
        
        # Background preloading
        self.image_cache = OrderedDict()
        self.max_cache_size = 200
        self.preload_queue = queue.Queue()
        self.preload_thread = threading.Thread(target=self._preload_worker, daemon=True)
        self.preload_thread.start()
        
        # Overlay navigation chevrons (Borderless style)
        self.btn_prev_overlay = RoundedButton(
            self.canvas, text="◀", width=36, height=72, radius=6,
            normal_color="#26262e", hover_color="#363642", fg="white"
        )
        self.btn_prev_overlay.config(command=self.show_prev_image)
        
        self.btn_next_overlay = RoundedButton(
            self.canvas, text="▶", width=36, height=72, radius=6,
            normal_color="#26262e", hover_color="#363642", fg="white"
        )
        self.btn_next_overlay.config(command=self.show_next_image)
        
        # RIGHT SIDE DRAWER SIDEBAR PANEL
        self.sidebar_frame = tk.Frame(
            self.display_frame,
            bg=self.clr_panel,
            width=340
        )
        # Prevent automatic resizing to preserve exact custom layout
        self.sidebar_frame.pack_propagate(False)
        self.sidebar_frame.grid_propagate(False)
        
        # Title of Drawer Panel
        self.sidebar_header = tk.Frame(self.sidebar_frame, bg=self.clr_panel)
        self.sidebar_header.pack(fill=tk.X, padx=16, pady=(15, 10))
        
        self.lbl_sidebar_title = tk.Label(
            self.sidebar_header,
            text="Info",
            bg=self.clr_panel,
            fg="white",
            font=("Segoe UI Variable Display", 13, "bold")
        )
        self.lbl_sidebar_title.pack(side=tk.LEFT)
        
        # Close Drawer Button
        self.btn_close_sidebar = RoundedButton(
            self.sidebar_header,
            text="✕",
            width=28,
            height=28,
            radius=5,
            normal_color=self.clr_panel,
            hover_color=self.clr_button_hover,
            fg="white",
            command=self.toggle_sidebar
        )
        self.btn_close_sidebar.pack(side=tk.RIGHT)
        
        # Inner Content Panel (Scrollable/Padded)
        self.sidebar_content = tk.Frame(self.sidebar_frame, bg=self.clr_panel)
        self.sidebar_content.pack(fill=tk.BOTH, expand=True, padx=16, pady=5)
        
        # Bottom Status Bar / Footer (Borders removed)
        self.bottom_frame = tk.Frame(
            root, 
            bg=self.clr_panel, 
            height=45
        )
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        
        # Left Footer Container
        self.left_footer = tk.Frame(self.bottom_frame, bg=self.clr_panel)
        self.left_footer.grid(row=0, column=0, padx=15, pady=6, sticky="w")
        
        footer_btn_style = {
            "normal_color": self.clr_panel,
            "hover_color": self.clr_button_hover,
            "fg": "white",
            "font": ("Segoe UI Variable Display", 11)
        }
        
        # Info Button (Toggles sidebar drawer)
        self.btn_info = RoundedButton(
            self.left_footer, text="ⓘ", width=28, height=28, radius=5,
            command=self.toggle_sidebar, **footer_btn_style
        )
        self.btn_info.pack(side=tk.LEFT, padx=2)
        ToolTip(self.btn_info, "Properties (I)")
        
        # Separation dot
        self.lbl_dot = tk.Label(self.left_footer, text="•", bg=self.clr_panel, fg="#888888", font=("Arial", 11))
        self.lbl_dot.pack(side=tk.LEFT, padx=5)
        
        # Dimensions & Size Label
        self.lbl_metadata = tk.Label(self.left_footer, text="", bg=self.clr_panel, fg="#cccccc", font=("Segoe UI Variable Display", 9))
        self.lbl_metadata.pack(side=tk.LEFT, padx=2)
        
        # Center Footer Container (Spacer)
        self.center_footer = tk.Frame(self.bottom_frame, bg=self.clr_panel)
        self.center_footer.grid(row=0, column=1, sticky="nsew")
        
        # Right Footer Container
        self.right_footer = tk.Frame(self.bottom_frame, bg=self.clr_panel)
        self.right_footer.grid(row=0, column=2, padx=15, pady=6, sticky="e")
        
        # Delete Button (Relocated to right footer)
        self.btn_delete = RoundedButton(
            self.right_footer, text="🗑", width=28, height=28, radius=5,
            command=self.delete_current_image, **footer_btn_style
        )
        self.btn_delete.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_delete, "Delete photo permanently (Del)")
        
        # Rotate Button (Relocated to right footer)
        self.btn_rotate = RoundedButton(
            self.right_footer, text="⟳", width=28, height=28, radius=5,
            command=self.rotate_image, **footer_btn_style
        )
        self.btn_rotate.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_rotate, "Rotate 90° clockwise (R)")
        
        # Fit Button (Relocated to right footer as an icon)
        self.btn_quick_fit = RoundedButton(
            self.right_footer, text="⛶", width=28, height=28, radius=5,
            command=self.zoom_to_fit, **footer_btn_style
        )
        self.btn_quick_fit.pack(side=tk.LEFT, padx=3)
        ToolTip(self.btn_quick_fit, "Fit image to screen")
        
        # Dropdown style Zoom label (100% ⋁)
        self.lbl_zoom = tk.Label(self.right_footer, text="100% ⋁", bg=self.clr_panel, fg="white", font=("Segoe UI Variable Display", 9), width=8, cursor="hand2")
        self.lbl_zoom.pack(side=tk.LEFT, padx=3)
        self.lbl_zoom.bind("<Button-1>", lambda e: self.zoom_to_fit())
        
        self.btn_scale_down = RoundedButton(
            self.right_footer, text="➖", width=28, height=28, radius=5,
            normal_color=self.clr_panel, hover_color=self.clr_button_hover, fg="white",
            command=self.zoom_out, font=("Segoe UI Variable Display", 11)
        )
        self.btn_scale_down.pack(side=tk.LEFT, padx=1)
        
        # Horizontal Zoom Slider
        self.zoom_slider = tk.Scale(
            self.right_footer,
            from_=5,
            to=400,
            orient=tk.HORIZONTAL,
            bg=self.clr_panel,
            fg="white",
            highlightthickness=0,
            troughcolor="#3d3d3d",
            activebackground=self.clr_accent_hover,
            sliderlength=10,
            width=10,
            length=100,
            showvalue=0,
            command=self.on_slider_move
        )
        self.zoom_slider.set(100)
        self.zoom_slider.pack(side=tk.LEFT, padx=5)
        
        # Zoom In Button
        self.btn_scale_up = RoundedButton(
            self.right_footer, text="➕", width=28, height=28, radius=5,
            normal_color=self.clr_panel, hover_color=self.clr_button_hover, fg="white",
            command=self.zoom_in, font=("Segoe UI Variable Display", 11)
        )
        self.btn_scale_up.pack(side=tk.LEFT, padx=1)
        
        # Mouse bindings for panning
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.pan)
        self.canvas.bind("<ButtonRelease-1>", self.end_pan)
        
        # Mouse bindings for zooming
        self.canvas.bind("<MouseWheel>", self.mouse_zoom)
        self.canvas.bind("<Button-4>", self.mouse_zoom)
        self.canvas.bind("<Button-5>", self.mouse_zoom)
        
        # Double click to toggle Fullscreen
        self.canvas.bind("<Double-Button-1>", self.toggle_fullscreen)
        
        # Configure event for resizing
        self.canvas.bind("<Configure>", self.on_resize)
        
        # Key bindings for keyboard shortcuts
        self.root.bind("<Right>", self.show_next_image)
        self.root.bind("<Left>", self.show_prev_image)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.root.bind("<Up>", lambda e: self.zoom_in())
        self.root.bind("<Down>", lambda e: self.zoom_out())
        self.root.bind("<Control-o>", lambda e: self.open_heic())
        self.root.bind("<Control-O>", lambda e: self.open_heic())
        self.root.bind("<Control-p>", lambda e: self.print_image())
        self.root.bind("<Control-P>", lambda e: self.print_image())
        self.root.bind("<Delete>", lambda e: self.delete_current_image())
        self.root.bind("<r>", lambda e: self.rotate_image())
        self.root.bind("<R>", lambda e: self.rotate_image())
        self.root.bind("<i>", lambda e: self.toggle_sidebar())
        self.root.bind("<I>", lambda e: self.toggle_sidebar())
        
        # Apply dark mode title bar
        self.set_dark_title_bar()
        
        # Silently register associations on startup
        self.register_association_silent()
        
        # Check command-line arguments to automatically load double-clicked files
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            if os.path.isfile(file_path) and file_path.lower().endswith(('.heic', '.heif')):
                self.root.after(100, lambda: self.load_initial_image(file_path))

    def register_association_silent(self):
        import winreg
        
        exe_path = os.path.abspath(sys.executable)
        if os.path.basename(exe_path).lower() in ("python.exe", "pythonw.exe"):
            return
            
        assoc_name = "HEICViewer.AssocFile"
        
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{assoc_name}") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "HEIC Image File")
                
            command_key_path = rf"Software\Classes\{assoc_name}\shell\open\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, command_key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
                
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.heic") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, assoc_name)
                
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.heif") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, assoc_name)
                
            app_path = rf"Software\Classes\Applications\heic_viewer.exe\shell\open\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
                
            uninstall_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HEICViewer"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_path) as key:
                winreg.SetValue(key, "DisplayName", winreg.REG_SZ, "HEIC Photo Viewer")
                winreg.SetValue(key, "UninstallString", winreg.REG_SZ, f'"{exe_path}" --uninstall')
                winreg.SetValue(key, "DisplayVersion", winreg.REG_SZ, "1.0.0")
                winreg.SetValue(key, "Publisher", winreg.REG_SZ, "HEIC Software")
                winreg.SetValue(key, "DisplayIcon", winreg.REG_SZ, exe_path)
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
                
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

    def toggle_sidebar(self, event=None):
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            # Highlight button when active
            self.btn_info.config(fg=self.clr_accent)
            self.sidebar_frame.grid(row=0, column=1, sticky="ns")
            self.populate_sidebar()
        else:
            self.btn_info.config(fg="white")
            self.sidebar_frame.grid_forget()
        
        # Trigger layout calculation to rescale canvas
        self.root.update_idletasks()
        if self.original_image:
            self.display_image()

    def populate_sidebar(self):
        # Clear sidebar content frame
        for widget in self.sidebar_content.winfo_children():
            widget.destroy()
            
        if not self.original_image or not self.folder_files:
            lbl = tk.Label(self.sidebar_content, text="No photo loaded.", bg=self.clr_panel, fg="#888888", font=("Segoe UI Variable Display", 10))
            lbl.pack(pady=20)
            return
            
        current_file = self.folder_files[self.current_index]
        
        # Extract file stats
        file_name = os.path.basename(current_file)
        file_name_no_ext = os.path.splitext(file_name)[0]
        size_str = get_file_size_str(current_file)
        w, h = self.original_image.size
        
        # Parse modification date/time as fallback
        mtime = os.path.getmtime(current_file)
        dt = datetime.datetime.fromtimestamp(mtime)
        day_str = str(dt.day)
        month_str = dt.strftime("%B")
        year_str = str(dt.year)
        hour_str = str(dt.hour)
        minute_str = dt.strftime("%M")
        
        # EXIF Variables
        exif = self.original_image.getexif()
        make_str = "Unknown Make"
        model_str = "Unknown Model"
        lens_focal = ""
        lens_aperture = ""
        exposure_time = ""
        iso_val = ""
        exposure_bias = ""
        flash_str = "No flash"
        
        if exif:
            # Check for standard date tags
            date_tag = exif.get(306) or exif.get(36867)
            if date_tag and isinstance(date_tag, str):
                try:
                    # Format: YYYY:MM:DD HH:MM:SS
                    dt_exif = datetime.datetime.strptime(date_tag.strip(), "%Y:%m:%d %H:%M:%S")
                    day_str = str(dt_exif.day)
                    month_str = dt_exif.strftime("%B")
                    year_str = str(dt_exif.year)
                    hour_str = str(dt_exif.hour)
                    minute_str = dt_exif.strftime("%M")
                except Exception:
                    pass
            
            # Read Camera Make and Model
            make_str = exif.get(271, make_str)
            model_str = exif.get(272, model_str)
            
            # Read detailed metadata values if present
            # Lens Model or lens descriptor
            if exif.get(37860): # Lens Model
                model_str = f"{model_str} ({exif.get(37860)})"
            if exif.get(37386): # Focal Length
                val = exif.get(37386)
                if isinstance(val, tuple) and len(val) == 2 and val[1] != 0:
                    lens_focal = f"{val[0]/val[1]:.1f} mm"
                else:
                    lens_focal = f"{val} mm"
            # Aperture F-Number
            if exif.get(33437):
                val = exif.get(33437)
                if isinstance(val, tuple) and len(val) == 2 and val[1] != 0:
                    lens_aperture = f"f/{val[0]/val[1]:.1f}"
                else:
                    lens_aperture = f"f/{val}"
            # Exposure time
            if exif.get(33434):
                val = exif.get(33434)
                if isinstance(val, tuple) and len(val) == 2 and val[1] != 0:
                    exposure_time = f"{val[0]}/{val[1]} sec"
                else:
                    exposure_time = f"{val} sec"
            # ISO Speed
            if exif.get(34855):
                iso_val = f"ISO {exif.get(34855)}"
            # Exposure Bias
            if exif.get(37380):
                val = exif.get(37380)
                if isinstance(val, tuple) and len(val) == 2 and val[1] != 0:
                    bias = val[0]/val[1]
                    exposure_bias = f"EXP {bias:+.1f}"
                else:
                    exposure_bias = f"EXP {val}"
            # Flash
            if exif.get(37385) is not None:
                flash_code = exif.get(37385)
                if flash_code & 1:
                    flash_str = "Flash fired"
                else:
                    flash_str = "No flash, compulsory"

        # Shared Style Properties for the Rounded Compartment Blocks
        box_bg = "#202026"
        box_border = "#2f2f3d"
        box_border_width = 1
        box_radius = 6
        box_height = 36
        box_width = 300
        
        # Helper to create horizontal row without left-side icons/emojis
        def create_sidebar_row(fill_content_func):
            row = tk.Frame(self.sidebar_content, bg=self.clr_panel)
            row.pack(fill=tk.X, pady=8)
            fill_content_func(row)
            
        # 1. Filename row (Segmented Single Box)
        def build_filename_row(parent):
            # Create rounded bg image
            self.img_filename_bg = make_rounded_segmented_image(box_width, box_height, box_radius, box_bg, box_border, box_border_width, [], self.clr_panel)
            
            lbl_bg = tk.Label(parent, image=self.img_filename_bg, bg=self.clr_panel, borderwidth=0, highlightthickness=0)
            lbl_bg.pack(fill=tk.X)
            lbl_bg.image = self.img_filename_bg # Keep reference
            
            entry = tk.Entry(lbl_bg, bg=box_bg, fg="white", relief="flat", insertbackground="white", font=("Segoe UI Variable Display", 10), justify=tk.CENTER)
            entry.insert(0, file_name_no_ext)
            entry.place(x=10, y=0, width=box_width - 20, height=box_height)
            entry.config(state="readonly", readonlybackground=box_bg)
            
        create_sidebar_row(build_filename_row)
        
        # 2. Date row (Three compartments inside a single rounded box)
        def build_date_row(parent):
            # Dividers at 15% (45px) and 73% (220px)
            self.img_date_bg = make_rounded_segmented_image(box_width, box_height, box_radius, box_bg, box_border, box_border_width, [0.15, 0.73], self.clr_panel)
            
            lbl_bg = tk.Label(parent, image=self.img_date_bg, bg=self.clr_panel, borderwidth=0, highlightthickness=0)
            lbl_bg.pack(fill=tk.X)
            lbl_bg.image = self.img_date_bg # Keep reference
            
            # Pack Day, Month, Year as borderless labels overlaying the background image compartments
            lbl_day = tk.Label(lbl_bg, text=day_str, bg=box_bg, fg="white", font=("Segoe UI Variable Display", 10), anchor="center")
            lbl_day.place(x=2, y=2, width=41, height=box_height-4)
            
            lbl_month = tk.Label(lbl_bg, text=month_str, bg=box_bg, fg="white", font=("Segoe UI Variable Display", 10), anchor="center")
            lbl_month.place(x=47, y=2, width=170, height=box_height-4)
            
            lbl_year = tk.Label(lbl_bg, text=year_str, bg=box_bg, fg="white", font=("Segoe UI Variable Display", 10), anchor="center")
            lbl_year.place(x=222, y=2, width=75, height=box_height-4)
            
        create_sidebar_row(build_date_row)
        
        # 3. Time row (Two compartments inside a single rounded box)
        def build_time_row(parent):
            # Divider in the middle (50% / 150px)
            self.img_time_bg = make_rounded_segmented_image(box_width, box_height, box_radius, box_bg, box_border, box_border_width, [0.5], self.clr_panel)
            
            lbl_bg = tk.Label(parent, image=self.img_time_bg, bg=self.clr_panel, borderwidth=0, highlightthickness=0)
            lbl_bg.pack(fill=tk.X)
            lbl_bg.image = self.img_time_bg # Keep reference
            
            # Pack Hour, Minute overlaying the background compartments
            lbl_hour = tk.Label(lbl_bg, text=hour_str, bg=box_bg, fg="white", font=("Segoe UI Variable Display", 10), anchor="center")
            lbl_hour.place(x=2, y=2, width=145, height=box_height-4)
            
            lbl_min = tk.Label(lbl_bg, text=minute_str, bg=box_bg, fg="white", font=("Segoe UI Variable Display", 10), anchor="center")
            lbl_min.place(x=152, y=2, width=145, height=box_height-4)
            
        create_sidebar_row(build_time_row)
        
        # 4. Description row (Segmented Single Box)
        def build_desc_row(parent):
            self.img_desc_bg = make_rounded_segmented_image(box_width, box_height, box_radius, box_bg, box_border, box_border_width, [], self.clr_panel)
            
            lbl_bg = tk.Label(parent, image=self.img_desc_bg, bg=self.clr_panel, borderwidth=0, highlightthickness=0)
            lbl_bg.pack(fill=tk.X)
            lbl_bg.image = self.img_desc_bg # Keep reference
            
            entry = tk.Entry(lbl_bg, bg=box_bg, fg="#888888", relief="flat", font=("Segoe UI Variable Display", 10), justify=tk.CENTER)
            entry.insert(0, "Add a description")
            entry.place(x=10, y=0, width=box_width - 20, height=box_height)
            
        create_sidebar_row(build_desc_row)
        
        # Divider Line
        tk.Frame(self.sidebar_content, height=1, bg="#2a2a32").pack(fill=tk.X, pady=12)
        
        # 5. Size Info section
        def build_size_row(parent):
            tk.Label(parent, text="Size Info", bg=self.clr_panel, fg="white", font=("Segoe UI Variable Display", 10, "bold"), anchor="w").pack(fill=tk.X)
            # Fetch resolution and density metrics
            dpi_val = self.original_image.info.get("dpi", (72, 72))
            dpi_str = f"{int(dpi_val[0])} dpi"
            bit_depth = 24 if self.original_image.mode == "RGB" else (32 if self.original_image.mode == "RGBA" else 8)
            
            val_txt = f"{w} x {h}    {size_str}    {dpi_str}    {bit_depth} bit"
            tk.Label(parent, text=val_txt, bg=self.clr_panel, fg="#888888", font=("Segoe UI Variable Display", 9), anchor="w", justify=tk.LEFT).pack(fill=tk.X, pady=(2, 0))
            
        create_sidebar_row(build_size_row)
        
        # 6. Device Info section
        def build_device_row(parent):
            tk.Label(parent, text="Device Info", bg=self.clr_panel, fg="white", font=("Segoe UI Variable Display", 10, "bold"), anchor="w").pack(fill=tk.X)
            
            # Format: Apple  iPhone 14  5.7 mm  f/1.5  1/50 sec
            #         ISO 640  EXP 0  No flash, compulsory
            dev_metrics = [make_str, model_str, lens_focal, lens_aperture, exposure_time]
            dev_line1 = "   ".join([x for x in dev_metrics if x])
            
            settings_metrics = [iso_val, exposure_bias, flash_str]
            dev_line2 = "   ".join([x for x in settings_metrics if x])
            
            val_txt = f"{dev_line1}\n{dev_line2}"
            tk.Label(parent, text=val_txt, bg=self.clr_panel, fg="#888888", font=("Segoe UI Variable Display", 9), anchor="w", justify=tk.LEFT).pack(fill=tk.X, pady=(2, 0))
            
        create_sidebar_row(build_device_row)
        
        # 7. Source section
        def build_source_row(parent):
            tk.Label(parent, text="Source", bg=self.clr_panel, fg="white", font=("Segoe UI Variable Display", 10, "bold"), anchor="w").pack(fill=tk.X)
            tk.Label(parent, text="This PC", bg=self.clr_panel, fg="#888888", font=("Segoe UI Variable Display", 9), anchor="w").pack(fill=tk.X, pady=(2, 0))
            
        create_sidebar_row(build_source_row)
        
        # 8. File Path section
        def build_filepath_row(parent):
            tk.Label(parent, text="File Path", bg=self.clr_panel, fg="white", font=("Segoe UI Variable Display", 10, "bold"), anchor="w").pack(fill=tk.X)
            
            path_row = tk.Frame(parent, bg=self.clr_panel)
            path_row.pack(fill=tk.X, pady=(2, 0))
            
            lbl_path = tk.Label(path_row, text=current_file, bg=self.clr_panel, fg="#f08060", font=("Segoe UI Variable Display", 9), anchor="w", justify=tk.LEFT, wraplength=270)
            lbl_path.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Copy path button (⎘)
            btn_copy = RoundedButton(
                path_row, text="⎘", width=24, height=24, radius=4,
                normal_color=self.clr_panel, hover_color=self.clr_button_hover, fg="white",
                command=lambda: self.copy_to_clipboard(current_file),
                font=("Segoe UI Variable Display", 9)
            )
            btn_copy.pack(side=tk.RIGHT, padx=(5, 5))
            ToolTip(btn_copy, "Copy path to clipboard")
            
        create_sidebar_row(build_filepath_row)

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Copied", "File path successfully copied to clipboard.")

    def rotate_image(self):
        if not self.original_image:
            return
        self.original_image = self.original_image.rotate(-90, expand=True)
        self.display_image()
        # Update metadata in sidebar if open
        if self.sidebar_visible:
            self.populate_sidebar()

    def delete_current_image(self):
        if not self.original_image or not self.folder_files:
            return
            
        current_file = self.folder_files[self.current_index]
        if messagebox.askyesno("Delete Photo", f"Delete {os.path.basename(current_file)} permanently?"):
            try:
                self.folder_files.pop(self.current_index)
                os.remove(current_file)
                
                if self.folder_files:
                    self.current_index = self.current_index % len(self.folder_files)
                    self.load_image_by_path(self.folder_files[self.current_index])
                else:
                    self.original_image = None
                    self.canvas.delete("all")
                    self.lbl_filename.config(text="HEIC Photo Viewer")
                    self.lbl_metadata.config(text="")
                    self.btn_prev_overlay.place_forget()
                    self.btn_next_overlay.place_forget()
                    if self.sidebar_visible:
                        self.populate_sidebar()
                    messagebox.showinfo("Deleted", "Folder is now empty.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete photo: {e}")

    def print_image(self):
        if not self.folder_files or self.current_index < 0:
            return
        current_file = self.folder_files[self.current_index]
        try:
            os.startfile(current_file, "print")
        except Exception as e:
            messagebox.showerror("Print", f"Could not open print wizard: {e}")

    def share_image(self):
        if not self.folder_files or self.current_index < 0:
            return
        current_file = self.folder_files[self.current_index]
        self.root.clipboard_clear()
        self.root.clipboard_append(current_file)
        messagebox.showinfo("Share", f"Photo path copied to clipboard:\n{current_file}")

    def on_slider_move(self, val):
        if not self.original_image:
            return
        new_scale = float(val) / 100.0
        if abs(self.zoom_scale - new_scale) > 0.005:
            self.zoom_scale = new_scale
            self.view_mode = "manual"
            self.display_image(update_slider=False)

    def set_dark_title_bar(self):
        try:
            self.root.update()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_USE_IMMERSIVE_DARK_MODE, 
                ctypes.byref(value), 
                ctypes.sizeof(value)
            )
        except Exception as e:
            print(f"Failed to set dark title bar: {e}")

    def load_initial_image(self, file_path):
        folder_path = os.path.dirname(file_path)
        self.folder_files = sorted([
            os.path.join(folder_path, f) for f in os.listdir(folder_path)
            if f.lower().endswith(('.heic', '.heif'))
        ])
        
        try:
            self.current_index = self.folder_files.index(file_path)
        except ValueError:
            self.folder_files = [file_path]
            self.current_index = 0
            
        self.enqueue_preloads(clear_cache=True)
        self.load_image_by_path(file_path)

    def start_pan(self, event):
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(event.x, event.y)
        
    def pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        
    def end_pan(self, event):
        self.canvas.config(cursor="")

    def on_resize(self, event):
        if event.width == self.canvas_width and event.height == self.canvas_height:
            return
        self.canvas_width = event.width
        self.canvas_height = event.height
        if self.original_image:
            self.display_image()

    def mouse_zoom(self, event):
        if not self.original_image:
            return
            
        if event.num == 4 or event.delta > 0:
            scale_factor = 1.2
        elif event.num == 5 or event.delta < 0:
            scale_factor = 0.8
        else:
            scale_factor = 1.0
            
        new_scale = self.zoom_scale * scale_factor
        new_scale = max(0.05, min(new_scale, 8.0))
        
        if new_scale != self.zoom_scale:
            self.zoom_to_scale(new_scale, anchor_pos=(event.x, event.y))

    def zoom_to_scale(self, new_scale, anchor_pos=None):
        if not self.original_image:
            return
            
        old_scale = self.zoom_scale
        self.zoom_scale = new_scale
        self.view_mode = "manual"
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        old_w = int(self.original_image.width * old_scale)
        old_h = int(self.original_image.height * old_scale)
        
        new_w = int(self.original_image.width * new_scale)
        new_h = int(self.original_image.height * new_scale)
        
        old_x_offset = max(0, (canvas_width - old_w) // 2)
        old_y_offset = max(0, (canvas_height - old_h) // 2)
        
        new_x_offset = max(0, (canvas_width - new_w) // 2)
        new_y_offset = max(0, (canvas_height - new_h) // 2)
        
        target_left, target_top = 0, 0
        if anchor_pos:
            mx = self.canvas.canvasx(anchor_pos[0])
            my = self.canvas.canvasy(anchor_pos[1])
            
            rx = mx - old_x_offset
            ry = my - old_y_offset
            
            ratio = new_scale / old_scale
            new_rx = rx * ratio
            new_ry = ry * ratio
            
            new_mx = new_x_offset + new_rx
            new_my = new_y_offset + new_ry
            
            target_left = new_mx - anchor_pos[0]
            target_top = new_my - anchor_pos[1]
            
        self.display_image()
        
        if anchor_pos and (new_w > canvas_width or new_h > canvas_height):
            scroll_w = max(new_w, canvas_width)
            scroll_h = max(new_h, canvas_height)
            
            x_frac = max(0.0, min(1.0, target_left / scroll_w))
            y_frac = max(0.0, min(1.0, target_top / scroll_h))
            
            self.canvas.xview_moveto(x_frac)
            self.canvas.yview_moveto(y_frac)

    def display_image(self, update_slider=True):
        if not self.original_image:
            return
            
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 100: canvas_width = 750
        if canvas_height < 100: canvas_height = 630
        
        if self.view_mode == "fit":
            img_w, img_h = self.original_image.size
            ratio = min(canvas_width / img_w, canvas_height / img_h)
            self.zoom_scale = min(ratio, 1.0)
            if self.zoom_scale <= 0:
                self.zoom_scale = 1.0
                
        new_w = max(1, int(self.original_image.width * self.zoom_scale))
        new_h = max(1, int(self.original_image.height * self.zoom_scale))
        
        resized_image = self.original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        sharpened_image = resized_image.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))
        
        self.tk_image = ImageTk.PhotoImage(sharpened_image)
        
        self.canvas.delete("all")
        
        x_offset = max(0, (canvas_width - new_w) // 2)
        y_offset = max(0, (canvas_height - new_h) // 2)
        
        self.image_container = self.canvas.create_image(
            x_offset, 
            y_offset, 
            anchor=tk.NW, 
            image=self.tk_image
        )
        
        scroll_w = max(new_w, canvas_width)
        scroll_h = max(new_h, canvas_height)
        self.canvas.config(scrollregion=(0, 0, scroll_w, scroll_h))
        
        self.lbl_zoom.config(text=f"{int(self.zoom_scale * 100)}% ⋁")
        
        if update_slider:
            slider_cmd = self.zoom_slider.cget("command")
            self.zoom_slider.config(command="")
            slider_val = min(400, max(5, int(self.zoom_scale * 100)))
            self.zoom_slider.set(slider_val)
            self.zoom_slider.config(command=slider_cmd)
        
        # Display/hide overlay buttons if we have multiple files
        if self.folder_files and len(self.folder_files) > 1:
            self.btn_prev_overlay.place(relx=0.01, rely=0.5, anchor=tk.W)
            self.btn_next_overlay.place(relx=0.99, rely=0.5, anchor=tk.E)
        else:
            self.btn_prev_overlay.place_forget()
            self.btn_next_overlay.place_forget()

    def zoom_to_fit(self):
        if not self.original_image:
            return
        self.view_mode = "fit"
        self.display_image()

    def zoom_to_100(self):
        if not self.original_image:
            return
        self.zoom_to_scale(1.0)

    def zoom_in(self):
        if not self.original_image:
            return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        new_scale = min(self.zoom_scale * 1.25, 4.0)
        self.zoom_to_scale(new_scale, anchor_pos=(canvas_width // 2, canvas_height // 2))

    def zoom_out(self):
        if not self.original_image:
            return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        new_scale = max(self.zoom_scale * 0.8, 0.05)
        self.zoom_to_scale(new_scale, anchor_pos=(canvas_width // 2, canvas_height // 2))

    def load_image_by_path(self, file_path):
        try:
            if file_path in self.image_cache:
                self.original_image = self.image_cache[file_path]
                self.image_cache.move_to_end(file_path)
            else:
                heic_image = Image.open(file_path)
                
                icc_profile = heic_image.info.get("icc_profile")
                if icc_profile:
                    try:
                        input_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
                        srgb_profile = ImageCms.createProfile("sRGB")
                        heic_image = ImageCms.profileToProfile(heic_image, input_profile, srgb_profile)
                    except Exception as cms_err:
                        print(f"Color profile conversion warning: {cms_err}")
                
                heic_image.load()
                self.original_image = heic_image
                
                if len(self.image_cache) >= self.max_cache_size:
                    self.image_cache.popitem(last=False)
                self.image_cache[file_path] = heic_image
                
            self.view_mode = "fit"
            self.zoom_scale = 1.0
            
            self.display_image()
            
            # Update labels
            self.lbl_filename.config(text=os.path.basename(file_path))
            
            size_str = get_file_size_str(file_path)
            w, h = self.original_image.size
            self.lbl_metadata.config(text=f"{w} × {h} • {size_str}")
            
            if self.sidebar_visible:
                self.populate_sidebar()
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not open or render HEIC file:\n{str(e)}")

    def open_heic(self):
        file_paths = filedialog.askopenfilenames(
            title="Select HEIC Image(s)",
            filetypes=[("HEIC Files", "*.heic *.heif")]
        )
        
        if not file_paths:
            return
            
        if len(file_paths) > 1:
            self.folder_files = list(file_paths)
            self.current_index = 0
            self.enqueue_preloads(clear_cache=True)
            self.load_image_by_path(self.folder_files[0])
        else:
            file_path = file_paths[0]
            folder_path = os.path.dirname(file_path)
            self.folder_files = sorted([
                os.path.join(folder_path, f) for f in os.listdir(folder_path)
                if f.lower().endswith(('.heic', '.heif'))
            ])
            
            try:
                self.current_index = self.folder_files.index(file_path)
            except ValueError:
                self.folder_files = [file_path]
                self.current_index = 0
                
            self.enqueue_preloads(clear_cache=True)
            self.load_image_by_path(file_path)

    def open_folder(self):
        folder_path = filedialog.askdirectory(title="Select Folder with HEIC Images")
        
        if not folder_path:
            return
            
        self.folder_files = sorted([
            os.path.join(folder_path, f) for f in os.listdir(folder_path)
            if f.lower().endswith(('.heic', '.heif'))
        ])
        
        if not self.folder_files:
            messagebox.showinfo("No HEIC Files", "No HEIC or HEIF files found in the selected folder.")
            return
            
        self.current_index = 0
        self.enqueue_preloads(clear_cache=True)
        self.load_image_by_path(self.folder_files[0])

    def show_next_image(self, event=None):
        if not self.folder_files or len(self.folder_files) <= 1:
            return
        self.current_index = (self.current_index + 1) % len(self.folder_files)
        self.enqueue_preloads(clear_cache=False)
        self.load_image_by_path(self.folder_files[self.current_index])

    def show_prev_image(self, event=None):
        if not self.folder_files or len(self.folder_files) <= 1:
            return
        self.current_index = (self.current_index - 1) % len(self.folder_files)
        self.enqueue_preloads(clear_cache=False)
        self.load_image_by_path(self.folder_files[self.current_index])

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.top_frame.pack_forget()
            self.bottom_frame.pack_forget()
            self.sidebar_frame.grid_forget()
        else:
            self.top_frame.pack(side=tk.TOP, fill=tk.X)
            self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
            if self.sidebar_visible:
                self.sidebar_frame.grid(row=0, column=1, sticky="ns")
            self.root.focus_set()

    def exit_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.toggle_fullscreen()

    def _preload_worker(self):
        while True:
            file_path = self.preload_queue.get()
            if file_path is None:
                break
            if file_path not in self.image_cache:
                try:
                    heic_image = Image.open(file_path)
                    
                    icc_profile = heic_image.info.get("icc_profile")
                    if icc_profile:
                        try:
                            input_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
                            srgb_profile = ImageCms.createProfile("sRGB")
                            heic_image = ImageCms.profileToProfile(heic_image, input_profile, srgb_profile)
                        except Exception:
                            pass
                            
                    heic_image.load() # Decode image
                    
                    # Store in cache and maintain size limit
                    if len(self.image_cache) >= self.max_cache_size:
                        self.image_cache.popitem(last=False) # Remove oldest
                        
                    self.image_cache[file_path] = heic_image
                except Exception as e:
                    print(f"Failed to preload {file_path}: {e}")
            self.preload_queue.task_done()

    def enqueue_preloads(self, clear_cache=False):
        # Clear existing queue
        with self.preload_queue.mutex:
            self.preload_queue.queue.clear()
            
        if clear_cache:
            self.image_cache.clear()
            
        if not self.folder_files:
            return
            
        files_to_preload = []
        if self.current_index >= 0 and self.current_index < len(self.folder_files):
            if self.folder_files[self.current_index] not in self.image_cache:
                files_to_preload.append(self.folder_files[self.current_index])
            
        # Add surrounding files prioritizing nearest neighbors
        left = self.current_index - 1
        right = self.current_index + 1
        while left >= 0 or right < len(self.folder_files):
            if right < len(self.folder_files):
                if self.folder_files[right] not in self.image_cache:
                    files_to_preload.append(self.folder_files[right])
                right += 1
            if left >= 0:
                if self.folder_files[left] not in self.image_cache:
                    files_to_preload.append(self.folder_files[left])
                left -= 1
                
        for file_path in files_to_preload[:self.max_cache_size]:
            self.preload_queue.put(file_path)

if __name__ == "__main__":
    root = tk.Tk()
    app = HEICViewerApp(root)
    root.mainloop()