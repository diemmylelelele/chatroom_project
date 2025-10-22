"""
Login window for chatroom application.
Allows user to enter name and choose avatar before connecting.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os


class LoginWindow:
    """
    Login window for chatroom.
    
    Attributes:
        root: Tkinter root window
        username: Username entered by user
        avatar_id: ID of selected avatar (0-1)
        success: Flag indicating successful login
    """
    
    def __init__(self, root):
        """
        Initialize login window.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("ChatRoom Login")
        self.root.geometry("560x640")
        self.root.resizable(False, False)
        
        # Set window background color
        self.root.configure(bg="#f3f3f3")
        
        # Variables to store login information
        self.username = None
        self.avatar_id = 0  # Default avatar
        self.success = False
        
        # Store PhotoImage to avoid garbage collection
        self.avatar_images = []
        self.selected_avatar_border = []
        
        # Create widgets
        self._create_widgets()
        
    def _create_widgets(self):
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
        
        # Subtitle (Enter your name)
        subtitle_label = tk.Label(
            self.root,
            text="Enter your name",
            font=("Segoe UI", 11),
            bg="#f3f3f3",
            fg="#333333"
        )
        subtitle_label.pack(pady=(5, 6))
        
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
        
        # Blue underline below entry (to match mockup)
        underline = tk.Frame(username_frame, height=2, bg="#1976D2")
        underline.pack(fill="x", padx=20)
        self.username_entry.focus()
        
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
        
        # Frame for avatar grid (1 row x 2 columns)
        avatar_grid_frame = tk.Frame(self.root, bg="#f3f3f3")
        avatar_grid_frame.pack(pady=10)
        
        # Create 2 avatar buttons in grid (Avatar 1 and Avatar 2)
        for i in range(2):
            row = i // 2
            col = i % 2
            
            # Frame for each avatar (to add border when selected)
            avatar_frame = tk.Frame(
                avatar_grid_frame,
                bg="#f3f3f3",
                highlightthickness=4,
                highlightbackground="#f3f3f3"
            )
            avatar_frame.grid(row=row, column=col, padx=30, pady=10)
            
            # Load avatar image from file
            avatar_image = self._load_avatar_image(i)
            if avatar_image is None:
                # If load fails, use fallback
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
            
        # Highlight default avatar (avatar 0)
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
        
    def _load_avatar_image(self, index):
        """
        Load avatar image from file.
        
        Args:
            index: Avatar index (0-1)
            
        Returns:
            PhotoImage object or None if load fails
        """
        try:
            # Path to avatar image
            # Avatar 1-2 corresponds to "avatar 1.png" and "avatar 2.png"
            img_path = os.path.join(
                os.path.dirname(__file__),
                "img",
                f"avatar {index + 1}.png"
            )
            
            # Load and resize image
            img = Image.open(img_path)
            img = img.resize((140, 140), Image.Resampling.LANCZOS)
            
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Cannot load avatar {index + 1}: {e}")
            return None
    
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
        # Remove highlight from old avatar
        self.selected_avatar_border[self.avatar_id].configure(
            highlightbackground="#f0f0f0"
        )
        
        # Update new avatar_id
        self.avatar_id = avatar_id
        
        # Highlight new avatar
        frame.configure(highlightbackground="#2196F3")
        
        print(f"Selected Avatar {avatar_id + 1}")
    
    def _login(self):
        """
        Handle when user clicks Login button or presses Enter.
        Validate username and close window if valid.
        """
        # Get username from entry
        username = self.username_entry.get().strip()
        
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


def show_login():
    """
    Display login window and return username + avatar_id.
    
    Returns:
        tuple: (username, avatar_id) if login successful
        tuple: (None, None) if user closes window
    """
    root = tk.Tk()
    login_window = LoginWindow(root)
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
