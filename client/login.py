"""
Login window for chatroom application.
Allows user to enter name and choose avatar before connecting.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
from typing import Optional, List


class LoginWindow:
    """
    Login window for chatroom.
    
    Attributes:
        root: Tkinter root window
        username: Username entered by user
        avatar_id: ID of selected avatar (0-1)
        success: Flag indicating successful login
    """
    
    def __init__(self, root, error_message: Optional[str] = None):
        """
        Initialize login window.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("ChatRoom Login")
        self.root.geometry("560x640")
        # Allow resizing and start maximized for a full-screen experience
        try:
            self.root.resizable(True, True)
        except Exception:
            pass
        try:
            self.root.state("zoomed")
        except Exception:
            try:
                self.root.attributes("-fullscreen", True)
                # Immediately toggle off to keep window decorations while sized to screen
                self.root.after(100, lambda: self.root.attributes("-fullscreen", False))
            except Exception:
                pass
        
        # Set window background color
        self.root.configure(bg="#f3f3f3")
        
        # Variables to store login information
        self.username = None
        self.avatar_id = 0  # Default avatar
        self.success = False
        
        # Store PhotoImage to avoid garbage collection and related metadata
        self.avatar_images: List[ImageTk.PhotoImage] = []
        self.selected_avatar_border: List[tk.Frame] = []
        self.avatar_files: List[str] = []  # absolute paths of discovered avatar files
        
        # Create widgets
        self._create_widgets(initial_error=error_message)
        
    def _create_widgets(self, initial_error: Optional[str] = None):
        """
        Create all widgets for login window.
        Includes: title, username entry, avatar selection, login button.
        """
        # Title label
        title_label = tk.Label(
            self.root,
            text="Welcome to ChatRoom",
            font=("Segoe UI", 28, "bold"),
            bg="#f3f3f3",
            fg="#1f1f1f"
        )
        title_label.pack(pady=(30, 10))
        
        # (Removed separate subtitle label; we'll use placeholder text in the entry instead.)
        
        # Frame cho username input
        username_frame = tk.Frame(self.root, bg="#f3f3f3")
        username_frame.pack(pady=20, padx=40, fill="x")
        
        # Username entry
        self.username_entry = tk.Entry(
            username_frame,
            font=("Segoe UI", 12),
            relief="flat",
            bg="#ffffff",
            fg="#111111",
            insertbackground="#111111"
        )
        self.username_entry.pack(fill="x", ipady=6, padx=20)
        # Placeholder: "Enter your name" that remains until the first character is typed
        self._name_placeholder_text = "Enter your name"
        self._name_placeholder_active = True
        self._name_entry_fg = "#111111"
        self._name_placeholder_fg = "#9e9e9e"

        def _name_apply_placeholder():
            try:
                if not self.username_entry.get():
                    self._name_placeholder_active = True
                    self.username_entry.configure(fg=self._name_placeholder_fg)
                    self.username_entry.insert(0, self._name_placeholder_text)
            except Exception:
                pass

        def _name_remove_placeholder_if_typing(event=None):
            # Only clear when a real character is typed; keep placeholder otherwise
            try:
                if self._name_placeholder_active:
                    ch = getattr(event, "char", "")
                    # Printable character triggers removal
                    if ch and ch.isprintable():
                        self.username_entry.delete(0, "end")
                        self.username_entry.configure(fg=self._name_entry_fg)
                        self._name_placeholder_active = False
                    elif event and event.keysym in ("BackSpace", "Delete"):
                        # Ignore delete/backspace while placeholder is visible
                        return "break"
            except Exception:
                pass

        def _name_focus_out(_e=None):
            try:
                if not self.username_entry.get().strip():
                    self.username_entry.delete(0, "end")
                    _name_apply_placeholder()
            except Exception:
                pass

        # Initialize placeholder and bindings
        _name_apply_placeholder()
        self.username_entry.bind("<KeyPress>", _name_remove_placeholder_if_typing)
        self.username_entry.bind("<<Paste>>", lambda e: (_name_remove_placeholder_if_typing(e), None))
        self.username_entry.bind("<FocusOut>", _name_focus_out)
        
        # Blue underline below entry (to match mockup)
        underline = tk.Frame(username_frame, height=2, bg="#1976D2")
        underline.pack(fill="x", padx=20)
        self.username_entry.focus()

        # Inline error label (initially hidden/empty)
        self.error_label = tk.Label(
            username_frame,
            text=initial_error or "",
            font=("Segoe UI", 10),
            fg="#d32f2f",
            bg="#f3f3f3",
            anchor="w"
        )
        self.error_label.pack(fill="x", padx=20, pady=(6, 0))
        
        # Bind Enter key for login
        self.username_entry.bind("<Return>", lambda e: self._login())
        
        # Avatar selection label
        avatar_label = tk.Label(
            self.root,
            text="Select Your Avatar",
            font=("Segoe UI", 13, "bold"),
            bg="#f3f3f3",
            fg="#1f1f1f"
        )
        avatar_label.pack(pady=(10, 10))
        
        # Frame for avatar grid (scrollable if many)
        avatar_grid_outer = tk.Frame(self.root, bg="#f3f3f3")
        avatar_grid_outer.pack(pady=10, fill="both", expand=False)

        # Discover avatar image files in client/img
        self.avatar_files = self._find_avatar_files()
        if not self.avatar_files:
            # Fallback to 2 synthetic avatars if none found
            self.avatar_files = []

        # Grid container
        avatar_grid_frame = tk.Frame(avatar_grid_outer, bg="#f3f3f3")
        avatar_grid_frame.pack()

        # Decide number of columns
        cols = 4
        count = max(len(self.avatar_files), 2)

        for i in range(count):
            row = i // cols
            col = i % cols

            # Frame for each avatar (to add border when selected)
            avatar_frame = tk.Frame(
                avatar_grid_frame,
                bg="#f3f3f3",
                highlightthickness=4,
                highlightbackground="#f3f3f3"
            )
            avatar_frame.grid(row=row, column=col, padx=16, pady=10)

            # Load avatar image
            if i < len(self.avatar_files):
                avatar_image = self._load_avatar_image_by_path(self.avatar_files[i])
                if avatar_image is None:
                    avatar_image = self._create_fallback_avatar(i)
            else:
                avatar_image = self._create_fallback_avatar(i)

            self.avatar_images.append(avatar_image)

            # Avatar button
            avatar_btn = tk.Button(
                avatar_frame,
                image=avatar_image,
                cursor="hand2",
                command=lambda idx=i, frame=avatar_frame: self._select_avatar(idx, frame),
                relief="flat",
                bg="#ffffff",
                activebackground="#f0f0f0"
            )
            avatar_btn.pack()

            # Save reference to frame for updating border
            self.selected_avatar_border.append(avatar_frame)

        # Highlight default avatar (avatar 0) if available
        if self.selected_avatar_border:
            self.selected_avatar_border[0].configure(highlightbackground="#2196F3")
        
        # Login button
        login_btn = tk.Button(
            self.root,
            text="Login",
            font=("Segoe UI", 12, "bold"),
            bg="#2196F3",
            fg="white",
            cursor="hand2",
            command=self._login,
            relief="flat",
            padx=40,
            pady=10,
            activebackground="#1976D2"
        )
        login_btn.pack(pady=30)

    def show_error(self, msg: str):
        """Display a red inline error under the username input."""
        try:
            self.error_label.config(text=msg)
        except Exception:
            pass
        
    def _load_avatar_image_by_path(self, img_path: str):
        """Load avatar image from an absolute path and resize to 140x140."""
        try:
            img = Image.open(img_path)
            img = img.resize((140, 140), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Cannot load avatar from {img_path}: {e}")
            return None

    def _find_avatar_files(self) -> List[str]:
        """Return a sorted list of avatar image file paths from client/img.

        Files matching pattern 'avatar <number>.png' will be sorted by the number.
        Other png files with 'avatar' prefix are appended afterward in name order.
        """
        # Avatar images are stored under client/img/avatar
        img_dir = os.path.join(os.path.dirname(__file__), "img", "avatar")
        files: List[str] = []
        try:
            for name in os.listdir(img_dir):
                lower = name.lower()
                if lower.endswith(('.png', '.jpg', '.jpeg')):
                    files.append(os.path.join(img_dir, name))
        except Exception as e:
            print(f"Error reading avatar directory: {e}")
            return []

        import re
        def sort_key(path: str):
            base = os.path.basename(path).lower()
            m = re.search(r"avatar\s*(\d+)", base)
            return (0, int(m.group(1))) if m else (1, base)

        files.sort(key=sort_key)
        return files
    
    def _create_fallback_avatar(self, index):
        """
        Create fallback avatar if loading from file fails.
        
        Args:
            index: Avatar index (0-1)
            
        Returns:
            PhotoImage object
        """
        # Color for each avatar
        colors = ["#FFB6C1", "#ADD8E6"]
        
        # Create simple image with color
        img = Image.new("RGB", (140, 140), colors[index % len(colors)])
        return ImageTk.PhotoImage(img)
    
    def _select_avatar(self, avatar_id, frame):
        """
        Handle when user selects an avatar.
        
        Args:
            avatar_id: ID of selected avatar (0-5)
            frame: Frame containing avatar button (for updating border)
        """
        # Remove highlight from old avatar (guard against out-of-range)
        try:
            self.selected_avatar_border[self.avatar_id].configure(
                highlightbackground="#f0f0f0"
            )
        except Exception:
            pass
        
        # Update new avatar_id
        self.avatar_id = avatar_id
        
        # Highlight new avatar
        frame.configure(highlightbackground="#2196F3")

        # Debug log
        print(f"Selected Avatar index {avatar_id}")
    
    def _login(self):
        """
        Handle when user clicks Login button or presses Enter.
        Validate username and close window if valid.
        """
        # Get username from entry
        val = self.username_entry.get()
        if getattr(self, "_name_placeholder_active", False) or val == self._name_placeholder_text:
            username = ""
        else:
            username = val.strip()
        
        # Validate username
        if not username:
            messagebox.showerror(
                "Error",
                "Please enter a username!"
            )
            self.username_entry.focus()
            return
        
        if len(username) < 2:
            messagebox.showerror(
                "Error",
                "Username must be at least 2 characters!"
            )
            self.username_entry.focus()
            return
        
        if len(username) > 20:
            messagebox.showerror(
                "Error",
                "Username must not exceed 20 characters!"
            )
            self.username_entry.focus()
            return
        
        # Check special characters
        if not username.replace("_", "").replace("-", "").replace(" ", "").isalnum():
            messagebox.showerror(
                "Error",
                "Username can only contain letters, numbers, underscores and hyphens!"
            )
            self.username_entry.focus()
            return
        
        # Save information and close window
        self.username = username
        self.success = True
        print(f"Login successful: {username} (Avatar {self.avatar_id + 1})")
        self.root.destroy()


def show_login(error_message: Optional[str] = None):
    """
    Display login window and return username + avatar_id.
    
    Returns:
        tuple: (username, avatar_id) if login successful
        tuple: (None, None) if user closes window
    """
    root = tk.Tk()
    login_window = LoginWindow(root, error_message)
    root.mainloop()
    
    if login_window.success:
        return login_window.username, login_window.avatar_id
    return None, None


if __name__ == "__main__":
    # Test login window
    username, avatar_id = show_login()
    if username:
        print(f"Logged in as: {username}, Avatar: {avatar_id + 1}")
    else:
        print("Login cancelled")
