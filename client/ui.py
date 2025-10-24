import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime, os, uuid
import emoji
from typing import Dict, Any, Optional
from PIL import Image, ImageTk

from common.crypto import decrypt_body

CHUNK = 32 * 1024 

class ChatUI(tk.Tk):
    def __init__(self, username: str, net, avatar_id: int = 0):
        super().__init__()
        self.title("FUV Chatroom")
        self.geometry("900x600")
        self.username = username
        self.avatar_id = avatar_id  # Current user's avatar ID
        self.net = net
        
        # Dictionary to store avatar images to prevent garbage collection
        self.avatar_images = {}
        self.user_avatars = {}  # username -> avatar_id mapping

        # right pane / user list
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0, minsize=150)
        self.rowconfigure(1, weight=1)

        header_text = f"FUV Chatroom  |  User: {self.username}"
        header = tk.Label(self, text=header_text, bg="#a1ecf7", font=("Segoe UI", 16, "bold"))
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(4,6))

        # message area
        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=(8,4))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.text = tk.Text(frame, state="disabled", wrap="word")
        self.text.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=sb.set)

        # user list - replaced Listbox with Canvas to draw avatar + name
        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(4,8))
        ttk.Label(right, text="ACTIVE", background="#a1ecf7", anchor="center", font=("Segoe UI", 10, "bold")).pack(fill="x")
        
        # Canvas with scrollbar for userlist
        canvas_frame = ttk.Frame(right)
        canvas_frame.pack(fill="both", expand=True, pady=4)
        
        self.user_canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0, width=150)
        user_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.user_canvas.yview)
        self.user_canvas.configure(yscrollcommand=user_scrollbar.set)
        
        self.user_canvas.pack(side="left", fill="both", expand=True)
        user_scrollbar.pack(side="right", fill="y")
        
        # Frame inside canvas to contain user items
        self.user_frame = tk.Frame(self.user_canvas, bg="white")
        self.canvas_window = self.user_canvas.create_window((75, 0), window=self.user_frame, anchor="n")
        
        # Bind to update scroll region and center window
        def update_canvas(e):
            self.user_canvas.configure(scrollregion=self.user_canvas.bbox("all"))
            # Center the window horizontally
            canvas_width = self.user_canvas.winfo_width()
            self.user_canvas.coords(self.canvas_window, canvas_width // 2, 0)
        
        self.user_frame.bind("<Configure>", update_canvas)
        self.user_canvas.bind("<Configure>", update_canvas)
        
        # Store reference for selection
        self.users = tk.Listbox(right)  # Keep for backward compatibility with old code
        self.users.pack_forget()  # Hide, not used anymore
        self.selected_user = None  # Track selected user

        # compose area
        compose = ttk.Frame(self)
        compose.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        compose.columnconfigure(0, weight=1)

        self.entry = ttk.Entry(compose)
        self.entry.grid(row=0, column=0, sticky="ew", ipady=6)
        self.entry.bind("<Return>", lambda e: self.send_text())

        # Load icons for emoji and file buttons
        self._load_button_icons()

        # Emoji button with icon
        emoji_btn = ttk.Button(compose, image=self.emoji_icon, command=self.open_emoji_picker)
        emoji_btn.grid(row=0, column=1, padx=4)
        
        # File button with icon
        file_btn = ttk.Button(compose, image=self.file_icon, command=self.send_file)
        file_btn.grid(row=0, column=2, padx=4)
        
        # Send Button
        ttk.Button(compose, text="Send ➤", command=self.send_text, width=12).grid(row=0, column=3, padx=4, ipady=8)

        # Prefer a font with colored emoji on Windows
        try:
            emoji_font = ("Segoe UI Emoji", 11)
            self.entry.configure(font=emoji_font)
            self.text.configure(font=emoji_font)
        except Exception:
            pass

        self.current_downloads: Dict[str, dict] = {}  # file_id -> {"name":..., "chunks":{}}
        self.current_upload: Optional[dict] = None    # {"path": str}

        # NOW attach the message handler - this will flush any backlogged messages
        # All widgets are created, so callbacks can safely update the UI
        self.net.on_message = self._on_message

    def _load_button_icons(self):
        """
        Load icons emoji_button.png, file_button.png and download_button.png from client/img folder
        """
        try:
            # Path to img folder (in client folder)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            img_dir = os.path.join(current_dir, "img")
            
            # Load emoji_button.png
            emoji_path = os.path.join(img_dir, "emoji_button.png")
            emoji_img = Image.open(emoji_path)
            # Resize to 28x28 pixels
            emoji_img = emoji_img.resize((28, 28), Image.Resampling.LANCZOS)
            self.emoji_icon = ImageTk.PhotoImage(emoji_img)
            
            # Load file_button.png
            file_path = os.path.join(img_dir, "file_button.png")
            file_img = Image.open(file_path)
            file_img = file_img.resize((28, 28), Image.Resampling.LANCZOS)
            self.file_icon = ImageTk.PhotoImage(file_img)
            
            # Load download_button.png
            download_path = os.path.join(img_dir, "download_button.png")
            download_img = Image.open(download_path)
            download_img = download_img.resize((24, 24), Image.Resampling.LANCZOS)
            self.download_icon = ImageTk.PhotoImage(download_img)
            
            print("✓ Successfully loaded button icons from client/img/")
            
        except Exception as e:
            # Fallback: if icons cannot be loaded
            print(f"⚠ Warning: Cannot load icons: {e}")
            print("  Using fallback icons...")
            
            # Create gray fallback icons
            fallback_img = Image.new('RGBA', (28, 28), (200, 200, 200, 255))
            self.emoji_icon = ImageTk.PhotoImage(fallback_img)
            self.file_icon = ImageTk.PhotoImage(fallback_img)
            self.download_icon = ImageTk.PhotoImage(fallback_img)
    
    def _load_avatar(self, avatar_id: int, size: int = 40):
        """
        Load avatar image from client/img and create circular shape
        
        Args:
            avatar_id: Avatar ID (0-1)
            size: Avatar size (default 40x40)
            
        Returns:
            PhotoImage of circular avatar
        """
        # Check cache first
        cache_key = f"{avatar_id}_{size}"
        if cache_key in self.avatar_images:
            return self.avatar_images[cache_key]
        
        try:
            # Path to avatar image
            current_dir = os.path.dirname(os.path.abspath(__file__))
            img_dir = os.path.join(current_dir, "img")
            img_path = os.path.join(img_dir, f"avatar {avatar_id + 1}.png")
            
            print(f"[DEBUG] Loading avatar: {img_path}, avatar_id={avatar_id}")  # Debug
            
            # Load and resize
            img = Image.open(img_path)
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (size, size), 0)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            
            # Apply mask
            img.putalpha(mask)
            
            # Convert to PhotoImage and save to cache
            photo = ImageTk.PhotoImage(img)
            self.avatar_images[cache_key] = photo
            return photo
            
        except Exception as e:
            print(f"Cannot load avatar {avatar_id + 1}: {e}")
            # Create fallback circular colored avatar
            colors = ["#FFB6C1", "#ADD8E6"]
            img = Image.new("RGBA", (size, size), colors[avatar_id % len(colors)] + "FF")
            
            # Create circular mask
            mask = Image.new('L', (size, size), 0)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            
            photo = ImageTk.PhotoImage(img)
            self.avatar_images[cache_key] = photo
            return photo

    def append(self, text: str, tag: Optional[str] = None):
        self.text.configure(state="normal")
        if tag == "system":
            self.text.insert("end", text + "\n", ("system",))
        elif tag == "private":
            self.text.insert("end", text + "\n", ("private",))
        elif tag == "public":
            self.text.insert("end", text + "\n", ("public",))
        else:
            self.text.insert("end", text + "\n")
        self.text.tag_config("system", foreground="gray")
        self.text.tag_config("private", foreground="#d06b00")
        self.text.tag_config("public", foreground="#2a64cb")
        self.text.configure(state="disabled")
        self.text.see("end")

    def _append_file_message_sent(self, filename: str, size: int):
        """
        Display file send notification on sender side (without Download button),
        with content format matching receiver side.
        """
        self.text.configure(state="normal")
        msg = f" {self.username} send file: {filename} ({self._format_size(size)}) \n"
        self.text.insert("end", msg, ("file_msg",))
        # Synchronize style with message on receiver side
        self.text.tag_config("file_msg", foreground="#FF6B35", font=("Segoe UI", 10, "bold"))
        self.text.configure(state="disabled")
        self.text.see("end")

    def _format_size(self, size_bytes: int) -> str:
        """
        Format file size to KB, MB, GB
        
        Args:
            size_bytes: File size in bytes
            
        Returns:
            Formatted string (e.g., "1.5 MB")
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _download_file(self, file_id: str):
        """
        Handle when user clicks download button
        
        Args:
            file_id: ID of file to download
        """
        if not hasattr(self, 'available_files') or file_id not in self.available_files:
            messagebox.showerror("Error", "File does not exist or has expired!")
            return
        
        file_info = self.available_files[file_id]
        
        # Send download request to sender
        self.net.send_file_ack(file_info['sender'], file_id, True)
        
        # Initialize download context
        self.current_downloads[file_id] = {
            "name": file_info['name'],
            "chunks": {},
            "next": 0
        }
        
        self.append(f"(System) Downloading file '{file_info['name']}' from {file_info['sender']}...", "system")

    def _show_file_offer_dialog(self, sender: str, filename: str, size: int, file_type: str, file_id: str):
        """
        Show a dialog asking user to accept or reject a file transfer.
        
        Args:
            sender: Username of the sender
            filename: Name of the file being offered
            size: Size of the file in bytes
            file_type: File extension/type
            file_id: Unique ID for this file transfer
        """
        # Format the message
        size_str = self._format_size(size)
        msg = f"{sender} wants to send you a file:\n\n"
        msg += f"Filename: {filename}\n"
        msg += f"Size: {size_str}\n"
        msg += f"Type: {file_type}\n\n"
        msg += "Do you want to accept this file?"
        
        # Show Yes/No dialog
        result = messagebox.askyesno(
            "Incoming File",
            msg,
            parent=self
        )
        
        if result:
            # User accepted - send ACK and start download
            self.append(f"(System) ({self.ts()}) Accepting file '{filename}' from {sender}...", "system")
            self.net.send_file_ack(sender, file_id, True)
            
            # Initialize download context
            self.current_downloads[file_id] = {
                "name": filename,
                "chunks": {},
                "next": 0
            }
        else:
            # User declined - send rejection ACK
            self.append(f"(System) ({self.ts()}) Declined file '{filename}' from {sender}.", "system")
            self.net.send_file_ack(sender, file_id, False)
            # Remove from available files
            if hasattr(self, 'available_files') and file_id in self.available_files:
                del self.available_files[file_id]

    def ts(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def send_text(self):
        raw = self.entry.get().strip()
        if not raw:
            return
        self.entry.delete(0, "end")

        # command: /w <user> message   → private
        if raw.startswith("/w "):
            try:
                rest = raw[3:].strip()
                target, msg = rest.split(" ", 1)
                msg = emoji.emojize(msg, language="alias")
                self.net.send_private(target, msg)
                self.append(f"(Private) (To {target}) ({self.ts()}): {msg}", "private")
            except ValueError:
                messagebox.showerror("Format", "Use: /w <username> <message>")
            return

        # if a user is selected, send private; otherwise public
        if self.selected_user:
            target = self.selected_user
            if target == self.username:
                self.append("(System) You cannot private-message yourself.", "system")
                return
            msg = emoji.emojize(raw, language="alias")
            self.net.send_private(target, msg)
            self.append(f"(Private) (To {target}) ({self.ts()}): {msg}", "private")
        else:
            msg = emoji.emojize(raw, language="alias")
            self.net.send_public(msg)

    # ========== Emoji picker UI ==========
    def open_emoji_picker(self):
        """
        Open emoji picker window with search bar, scrollbar and emoji grid display
        """
        # Prevent opening multiple emoji picker windows at once
        if getattr(self, "_emoji_win", None) and tk.Toplevel.winfo_exists(self._emoji_win):
            self._emoji_win.lift()  # Bring already open window to front
            return

        # Create new Toplevel window
        win = tk.Toplevel(self)
        self._emoji_win = win
        win.title("Pick an emoji")
        win.transient(self)  # Attach to main window
        win.resizable(False, False)  # Don't allow resize
        
        # Position window near mouse cursor (near emoji button)
        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            win.geometry(f"360x280+{x-190}+{y-350}")
        except Exception:
            win.geometry("360x280")

        # Close window when Escape key is pressed
        win.bind("<Escape>", lambda e: win.destroy())

        # Save cursor position in entry to insert emoji at correct position
        try:
            self._emoji_insert_pos = self.entry.index("insert")
        except Exception:
            self._emoji_insert_pos = None

        # ===== SEARCH BAR =====
        top = ttk.Frame(win)
        top.pack(fill="x", padx=8, pady=(8,4))
        ttk.Label(top, text="Search:").pack(side="left")
        query = tk.StringVar(master=win)
        ent = ttk.Entry(top, textvariable=query)
        ent.pack(side="left", fill="x", expand=True, padx=(6,0))

        # ===== SCROLLABLE CANVAS FOR GRID =====
        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=8, pady=(0,8))
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)
        
        # Update scroll region when frame size changes
        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Embed frame into canvas and keep window id for resize
        window_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Synchronize frame width with canvas to avoid horizontal clipping
        def _on_canvas_config(e):
            try:
                canvas.itemconfigure(window_id, width=e.width)
            except Exception:
                pass

        canvas.bind("<Configure>", _on_canvas_config)

        # ===== MOUSE WHEEL SCROLLING =====
        def _on_mousewheel(event):
            try:
                if hasattr(event, 'delta') and event.delta:
                    # Windows/macOS: event.delta is positive/negative number
                    step = -1 * int(event.delta / 120)
                    canvas.yview_scroll(step, 'units')
                elif hasattr(event, 'num'):
                    # X11 (Linux): Button-4 (up), Button-5 (down)
                    if event.num == 4:
                        canvas.yview_scroll(-1, 'units')
                    elif event.num == 5:
                        canvas.yview_scroll(1, 'units')
            except Exception:
                pass

        def _bind_mousewheel(_e):
            # Bind mouse wheel when cursor enters canvas
            import sys
            if sys.platform.startswith('linux'):
                canvas.bind_all('<Button-4>', _on_mousewheel)
                canvas.bind_all('<Button-5>', _on_mousewheel)
            else:
                canvas.bind_all('<MouseWheel>', _on_mousewheel)

        def _unbind_mousewheel(_e):
            # Unbind mouse wheel when cursor leaves canvas
            import sys
            if sys.platform.startswith('linux'):
                canvas.unbind_all('<Button-4>')
                canvas.unbind_all('<Button-5>')
            else:
                canvas.unbind_all('<MouseWheel>')

        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)

        # ===== BUILD EMOJI BUTTONS =====
        # Style for emoji buttons with large font
        style = ttk.Style(win)
        try:
            style.configure("Emoji.TButton", font=("Segoe UI Emoji", 16), padding=(4, 2))
        except Exception:
            style.configure("Emoji.TButton", padding=(4, 2))
        
        # Get list of all emojis
        all_items = self._emoji_items()

        def render(items):
            """
            Render grid of emoji buttons
            Args:
                items: List of (symbol, code) tuples
            """
            # Delete all old buttons
            for child in frame.winfo_children():
                child.destroy()
            
            cols = 7  # 7 columns
            r = c = 0
            for sym, code in items:
                btn = ttk.Button(frame, text=sym, width=3, style="Emoji.TButton")
                
                # Insert emoji symbol into entry and close window when clicked
                def on_click(s=sym, w=win):
                    self._insert_symbol(s)
                    try:
                        w.destroy()
                    except Exception:
                        pass
                
                btn.configure(command=on_click)
                btn.grid(row=r, column=c, padx=4, pady=4)
                c += 1
                if c >= cols:
                    r += 1
                    c = 0

        def do_filter(*_):
            """
            Filter emojis by search keyword
            """
            q = query.get().strip().lower()
            if not q:
                # No query -> display all
                render(all_items)
                return
            # Filter emojis containing keyword in code (remove : and replace _ with space)
            filtered = [it for it in all_items if q in it[1].strip(":").replace("_", " ")]
            render(filtered)

        # Bind filter function with search entry
        query.trace_add("write", lambda *_: do_filter())
        
        # Render all emojis initially
        render(all_items)
        
        # Focus on search entry so user can type immediately
        ent.focus_set()

    def _insert_symbol(self, symbol: str):
        """
        Insert emoji symbol into entry at saved cursor position
        Args:
            symbol: Emoji symbol string (e.g., 😊)
        """
        try:
            # Focus on entry
            self.entry.focus_set()
            try:
                self.entry.update_idletasks()
            except Exception:
                pass
            
            # Set cursor at saved position (or end if none)
            pos = getattr(self, "_emoji_insert_pos", None)
            try:
                self.entry.icursor(pos if pos is not None else "end")
            except Exception:
                try:
                    self.entry.icursor("end")
                except Exception:
                    pass
            
            # Insert emoji symbol
            self.entry.insert("insert", symbol)
        except Exception:
            # Fallback: insert at end of entry
            try:
                self.entry.insert("end", symbol)
            except Exception:
                pass

    def _emoji_items(self):
        """
        Return list of popular emojis with symbol and code
        Returns:
            List of (symbol, code) tuples
            Example: [("😀", ":grinning:"), ("😊", ":smile:"), ...]
        """
        # List of popular emoji codes (alias format)
        codes = [
            ":grinning:", ":smiley:", ":smile:", ":grin:", ":sweat_smile:", ":joy:", ":rofl:",
            ":relaxed:", ":blush:", ":slightly_smiling_face:", ":upside_down_face:", ":wink:", ":relieved:", ":heart_eyes:", ":kissing_heart:",
            ":kissing:", ":kissing_smiling_eyes:", ":kissing_closed_eyes:", ":yum:", ":stuck_out_tongue:", ":stuck_out_tongue_winking_eye:",
            ":stuck_out_tongue_closed_eyes:", ":money_mouth_face:", ":hugs:", ":nerd_face:", ":sunglasses:", ":star_struck:",
            ":thinking:", ":zipper_mouth_face:", ":neutral_face:", ":expressionless:", ":no_mouth:", ":smirk:", ":unamused:",
            ":roll_eyes:", ":grimacing:", ":lying_face:", ":pensive:", ":sleepy:", ":sleeping:", ":sweat:",
            ":cry:", ":sob:", ":disappointed_relieved:", ":cold_sweat:", ":fearful:", ":scream:", ":confounded:", ":persevere:",
            ":triumph:", ":angry:", ":rage:", ":clap:", ":raised_hands:", ":wave:", ":thumbs_up:", ":thumbs_down:", ":ok_hand:",
            ":pray:", ":muscle:", ":heart:", ":orange_heart:", ":yellow_heart:", ":green_heart:", ":blue_heart:", ":purple_heart:",
            ":black_heart:", ":white_heart:", ":sparkles:", ":fire:", ":star:", ":zap:", ":tada:", ":confetti_ball:", ":rocket:",
        ]
        
        items = []
        for c in codes:
            try:
                # Convert emoji code to symbol
                items.append((emoji.emojize(c, language="alias"), c))
            except Exception:
                # Skip emoji if emojize fails
                pass
        return items

    def send_file(self):
        broadcast = False
        to_user = None
        
        # Use selected_user instead of Listbox selection
        if not self.selected_user:
            # No recipient selected → broadcast to everyone
            broadcast = True
        else:
            to_user = self.selected_user
            if to_user == self.username:
                messagebox.showinfo("Invalid", "You cannot send a file to yourself.")
                return
        
        path = filedialog.askopenfilename(title="Select file to send")
        if not path:
            return
        
        size = os.path.getsize(path)
        filename = os.path.basename(path)
        
        # Create unique file_id for this file
        file_id = str(uuid.uuid4())
        
        if broadcast:
            # Send to all users
            self.net.send_file_offer("*", path, size, file_id)
            self.append(f"(System) ({self.ts()}) Sending file '{filename}' ({self._format_size(size)}) to all users...", "system")
        else:
            # Send to specific user
            self.net.send_file_offer(to_user, path, size, file_id)
            self.append(f"(System) ({self.ts()}) Sending file '{filename}' ({self._format_size(size)}) to {to_user}...", "system")

        # Save file to be ready for upload when someone accepts
        self.current_upload = {"path": path, "file_id": file_id}

    # --------- incoming messages ----------
    def _on_message(self, env: Dict[str, Any]):
        t = env.get("type")
        if t == "system":
            # Include timestamp for system notifications (join/leave, etc.)
            self.append(f"(System) ({self._hhmm(env)}) {env['payload'].get('text','')}", "system")
            return
        if t == "userlist":
            users = env["payload"]["users"]
            
            # Delete all widgets in user_frame
            for widget in self.user_frame.winfo_children():
                widget.destroy()
            
            # Update user_avatars mapping
            self.user_avatars.clear()
            
            # Create item for each user with circular avatar + name
            for i, user_info in enumerate(users):
                # user_info can be dict {"username": ..., "avatar_id": ...} or string (legacy)
                if isinstance(user_info, dict):
                    username = user_info["username"]
                    avatar_id = user_info.get("avatar_id", 0)
                else:
                    username = user_info
                    avatar_id = 0
                
                self.user_avatars[username] = avatar_id
                print(f"[DEBUG] User: {username}, avatar_id: {avatar_id}")  # Debug
                
                # Create frame for each user item
                user_frame = tk.Frame(self.user_frame, bg="white", cursor="hand2")
                user_frame.pack(pady=3, anchor="center")
                
                # Load circular avatar
                avatar_img = self._load_avatar(avatar_id, size=40)
                
                # Avatar label
                avatar_label = tk.Label(user_frame, image=avatar_img, bg="white")
                avatar_label.image = avatar_img  # Keep reference
                avatar_label.pack(side="left", padx=(5, 10))
                
                # Username label
                name_label = tk.Label(user_frame, text=username, bg="white", font=("Segoe UI", 13), anchor="w")
                name_label.pack(side="left")
                
                # Bind click to select user (for private message or send file)
                user_frame.bind("<Button-1>", lambda e, u=username: self._select_user(u))
                avatar_label.bind("<Button-1>", lambda e, u=username: self._select_user(u))
                name_label.bind("<Button-1>", lambda e, u=username: self._select_user(u))
                
                # Highlight if this is the selected user
                if self.selected_user == username:
                    user_frame.config(bg="#e3f2fd")
                    avatar_label.config(bg="#e3f2fd")
                    name_label.config(bg="#e3f2fd")
            
            return
        
        # Call helper to process encrypted messages
        self._process_encrypted_message(env, t)
    
    def _select_user(self, username: str):
        """Select user from Active list"""
        self.selected_user = username
        
        # Update highlight in user list
        for widget in self.user_frame.winfo_children():
            if isinstance(widget, tk.Frame):
                is_selected = False
                for child in widget.winfo_children():
                    if isinstance(child, tk.Label) and child.cget("text") == username:
                        is_selected = True
                        break
                
                bg_color = "#e3f2fd" if is_selected else "white"
                widget.config(bg=bg_color)
                for child in widget.winfo_children():
                    child.config(bg=bg_color)
    
    def _process_encrypted_message(self, env: Dict[str, Any], t: str):
        """Process encrypted messages"""
        # encrypted payloads
        try:
            body = decrypt_body(self.net.session_key, env["payload"])
        except Exception:
            # during handshake some messages are plaintext or not for us
            return

        if t == "pub":
            self.append(f"(Global) ({self._hhmm(env)}) {env['sender']}: {body['text']}", "public")
        elif t == "priv":
            if env['to'] == self.username:
                self.append(f"(Private) (From {env['sender']}) ({self._hhmm(env)}): {body['text']}", "private")
        elif t == "file_offer":
            # Received notification that a file has been sent
            name = body["name"]
            size = body["size"]
            file_type = body.get("type", "unknown")
            sender = env['sender']
            file_id = body.get("file_id", str(uuid.uuid4()))
            
            # Save file information for later download
            if not hasattr(self, 'available_files'):
                self.available_files = {}
            
            self.available_files[file_id] = {
                "name": name,
                "size": size,
                "type": file_type,
                "sender": sender,
                "file_id": file_id
            }
            
            # Show accept/reject dialog to user
            self._show_file_offer_dialog(sender, name, size, file_type, file_id)
            
        elif t == "file_ack":
            if not body.get("accept"):
                # Receiver declined the file
                self.append(f"(System) ({self.ts()}) {env['sender']} declined your file.", "system")
            else:
                # Receiver accepted - start upload to the ACK sender (works for direct or broadcast offers)
                if not self.current_upload:
                    return
                fid = body["id"]
                path = self.current_upload["path"]
                to_user = env["sender"]
                
                # Show upload starting message
                self.append(f"(System) ({self.ts()}) Sending file to {to_user}...", "system")
                
                seq = 0
                with open(path, "rb") as f:
                    while True:
                        b = f.read(CHUNK)
                        if not b:
                            # send an empty final chunk marker (bytes)
                            self.net.send_file_chunk(to_user, fid, seq, b"", True)
                            break
                        # send raw bytes; NetClient will latin1-encode for JSON
                        self.net.send_file_chunk(to_user, fid, seq, b, False)
                        seq += 1
                self.append(f"(System) ({self.ts()}) Finished sending '{os.path.basename(path)}' to {to_user}.", "system")
        elif t == "file_chunk":
            fid, seq, final = body["id"], body["seq"], body["final"]
            ch = body["data"].encode("latin1")
            ctx = self.current_downloads.get(fid)
            if not ctx:
                # first chunk without offer? initialize
                self.current_downloads[fid] = ctx = {"name":"file.bin","chunks":{}, "next":0}
            ctx["chunks"][seq] = ch
            if final:
                # All chunks received - reconstruct file in order
                ordered = bytearray()
                for i in range(len(ctx["chunks"])):
                    ordered.extend(ctx["chunks"][i])
                
                # Ask user where to save the file
                save = filedialog.asksaveasfilename(
                    defaultextension="",
                    initialfile=ctx["name"],
                    title=f"Save file: {ctx['name']}"
                )
                
                if save:
                    with open(save, "wb") as f:
                        f.write(ordered)
                    self.append(f"(System) ({self.ts()}) File saved to: {save}", "system")
                else:
                    self.append(f"(System) ({self.ts()}) File download cancelled.", "system")
                
                # Clean up download context
                del self.current_downloads[fid]

    def _append_file_message(self, sender: str, filename: str, size: int, file_id: str):
        """
        Display file notification in chat like a normal message
        Format: (Global) {sender} sent a file: {filename}
        - Filename is underlined, bold and clickable to download
        - No separate download button needed
        """
        self.text.configure(state="normal")
        
        # Prefix part: (Global) sender sent a file: 
        prefix = f"(Global) {sender} sent a file: "
        self.text.insert("end", prefix, "public")
        
        # Filename: underlined + bold + clickable
        # Create unique tag for each file to bind click event
        file_tag = f"file_{file_id}"
        self.text.insert("end", filename, ("file_name", file_tag))
        
        # Configure style for filename
        self.text.tag_config("file_name", underline=True, font=("Segoe UI Emoji", 11, "bold"), foreground="#2a64cb")
        
        # Bind click event to this tag
        self.text.tag_bind(file_tag, "<Button-1>", lambda e, fid=file_id: self._download_file(fid))
        
        # Change cursor to hand when hovering
        self.text.tag_bind(file_tag, "<Enter>", lambda e: self.text.config(cursor="hand2"))
        self.text.tag_bind(file_tag, "<Leave>", lambda e: self.text.config(cursor=""))
        
        # New line after message
        self.text.insert("end", "\n")
        
        self.text.configure(state="disabled")
        self.text.see("end")

    def _download_file(self, file_id: str):
        """
        Handle when user clicks Download button
        """
        if not hasattr(self, 'available_files') or file_id not in self.available_files:
            messagebox.showwarning("Error", "File does not exist or has expired.")
            return
        
        file_info = self.available_files[file_id]
        sender = file_info["sender"]
        filename = file_info["name"]
        
        # Send ACK accepting download
        self.net.send_file_ack(sender, file_id, True)
        
        # Initialize context to receive chunks
        if not hasattr(self, 'current_downloads'):
            self.current_downloads = {}
        
        self.current_downloads[file_id] = {
            "name": filename,
            "chunks": {},
            "next": 0
        }
        
        self.append(f"(System) ({self.ts()}) Downloading file '{filename}' from {sender}...", "system")

    def _hhmm(self, env):
        '''Takes an env dict and returns a HH:MM:SS string in local time'''
        ts = env.get("ts")
        if not ts:
            return "--:--:--"
        try:
            s = ts
            # Support ISO strings with trailing 'Z' (UTC)
            if s.endswith("Z"):
                s = s.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(s)
            if dt.tzinfo is None:
                # Treat naive timestamps as UTC
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            local_dt = dt.astimezone()  # convert to local timezone
            return local_dt.strftime("%H:%M:%S")
        except Exception:
            # Fallback to substring if parsing fails
            try:
                return ts[11:19]
            except Exception:
                return "--:--:--"