import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import pillow_heif

# Register HEIC saving/loading capabilities with Pillow
pillow_heif.register_heif_opener()

class HEICMakerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HEIC Photo Maker")
        self.root.geometry("400x250")
        self.root.resizable(False, False)
        
        # UI Elements
        self.label = tk.Label(root, text="Convert PNG/JPEG to HEIC", font=("Arial", 14, "bold"), pady=10)
        self.label.pack()
        
        self.info_label = tk.Label(root, text="Select an image file to convert into HEIC format.", wraplength=350, fg="gray")
        self.info_label.pack(pady=10)
        
        self.btn_select = tk.Button(root, text="Choose Image & Convert", command=self.convert_image, bg="#007ACC", fg="white", font=("Arial", 11), padx=10, pady=5)
        self.btn_select.pack(pady=20)
        
        self.status_label = tk.Label(root, text="", fg="green", font=("Arial", 10))
        self.status_label.pack()

    def convert_image(self):
        # 1. Open file dialog to select input image
        file_path = filedialog.askopenfilename(
            title="Select Image File",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        
        if not file_path:
            return  # User cancelled selection
            
        try:
            self.status_label.config(text="Processing...", fg="blue")
            self.root.update_idletasks()
            
            # 2. Load the image using Pillow
            img = Image.open(file_path)
            
            # 3. Create the output HEIC filename
            base_path, _ = os.path.splitext(file_path)
            output_heic_path = base_path + ".heic"
            
            # 4. Save as HEIC format (Quality 0-100, where 80-90 matches pristine quality at tiny size)
            img.save(output_heic_path, format="HEIF", quality=85)
            
            # 5. Success Message
            filename = os.path.basename(output_heic_path)
            self.status_label.config(text=f"Success! Saved as {filename}", fg="green")
            messagebox.showinfo("Success", f"File successfully saved to:\n{output_heic_path}")
            
        except Exception as e:
            self.status_label.config(text="Error occurred.", fg="red")
            messagebox.showerror("Error", f"Failed to convert image:\n{str(e)}")

# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = HEICMakerApp(root)
    root.mainloop()