import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import os

class LoginWindow(tk.Tk):
    """Simple login window with name entry and avatar selection."""
    def __init__(self, on_login):
        super().__init__()
        self.title("ChatRoom - Login")
        self.geometry("600x700")
        self.resizable(False, False)
        self.on_login = on_login
        self.selected_avatar = None

        # --- Header ---
        tk.Label(self, text="Welcome to ChatRoom", font=("Segoe UI", 20, "bold")).pack(pady=30)

        # --- Name Entry ---
        ttk.Label(self, text="Enter your name", font=("Segoe UI", 10)).pack()
        self.name_entry = ttk.Entry(self, width=40, font=("Segoe UI", 11))
        self.name_entry.pack(pady=10)
        self.name_entry.focus()

        # --- Avatar Section ---
        tk.Label(self, text="Select Your Avatar", font=("Segoe UI", 12, "bold")).pack(pady=10)
        frame = ttk.Frame(self); frame.pack(pady=10)

        self.avatar_buttons, self.avatar_photos = [], []
        img_folder = os.path.join(os.path.dirname(__file__), "img")
        for i, filename in enumerate(["avatar 1.png", "avatar 2.png"]):
            path = os.path.join(img_folder, filename)
            img = self._make_circle_image(path)
            btn = tk.Button(frame, image=img, bg="#f5d5b8", relief="flat", cursor="hand2",
                            command=lambda f=filename: self._select_avatar(f))
            btn.grid(row=i//2, column=i%2, padx=20, pady=20)
            self.avatar_buttons.append((btn, filename))
            self.avatar_photos.append(img)

        # --- Login Button ---
        tk.Button(self, text="Login", font=("Segoe UI", 12, "bold"),
                  bg="#1e90ff", fg="white", width=15, relief="flat",
                  cursor="hand2", command=self._on_login_click).pack(pady=30)
        self.name_entry.bind("<Return>", lambda e: self._on_login_click())

    def _make_circle_image(self, path, size=100):
        """Load and crop an image into a circle."""
        try:
            img = Image.open(path).resize((size, size))
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _select_avatar(self, avatar):
        """Highlight selected avatar."""
        self.selected_avatar = avatar
        for btn, name in self.avatar_buttons:
            btn.config(bg="#1e90ff" if name == avatar else "#f5d5b8")

    def _on_login_click(self):
        """Validate and call login callback."""
        name = self.name_entry.get().strip()
        if not name:
            return messagebox.showwarning("Input Required", "Please enter your name.")
        if not self.selected_avatar:
            return messagebox.showwarning("Avatar Required", "Please select an avatar.")
        self.on_login(name, self.selected_avatar)

    def show_duplicate_error(self):
        """Show duplicate name error."""
        messagebox.showerror("Username Taken", "This username is already in use.")
        self.name_entry.focus()
        self.name_entry.select_range(0, "end")
