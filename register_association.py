import sys
import os
import winreg
import ctypes

def register_association():
    # Resolve absolute path to dist/heic_viewer.exe
    current_dir = os.path.dirname(os.path.abspath(__file__))
    exe_path = os.path.join(current_dir, "dist", "heic_viewer.exe")
    
    if not os.path.exists(exe_path):
        print(f"Error: Executable not found at {exe_path}.")
        print("Please build the executable using PyInstaller first.")
        input("\nPress Enter to exit...")
        return False
        
    print(f"Registering file association for: {exe_path}")
    
    assoc_name = "HEICViewer.AssocFile"
    
    try:
        # 1. Create HEICViewer.AssocFile structure under HKEY_CURRENT_USER\Software\Classes
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{assoc_name}") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "HEIC Image File")
            
        # HKEY_CURRENT_USER\Software\Classes\HEICViewer.AssocFile\shell\open\command
        command_key_path = rf"Software\Classes\{assoc_name}\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, command_key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
            
        # 2. Map extensions
        # HKEY_CURRENT_USER\Software\Classes\.heic
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.heic") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, assoc_name)
            
        # HKEY_CURRENT_USER\Software\Classes\.heif
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.heif") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, assoc_name)
            
        # 3. Add to Applications list so it shows up in Open With
        app_path = rf"Software\Classes\Applications\heic_viewer.exe\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
            
        # 4. Notify Windows Shell that file associations have changed
        # SHCNE_ASSOCCHANGED = 0x08000000, SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        
        print("\nSuccess! HEIC/HEIF file associations registered successfully.")
        print("You can now right-click a HEIC photo, go to 'Open With', select 'HEIC Photo Viewer', and check 'Always use this app'.")
        input("\nPress Enter to exit...")
        return True
    except Exception as e:
        print(f"\nError writing to registry: {e}")
        input("\nPress Enter to exit...")
        return False

if __name__ == "__main__":
    register_association()
