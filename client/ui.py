import os, sys, uuid, datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw
from typing import Optional, Dict, Any
import emoji

from common.crypto import decrypt_body

CHUNK = 32 * 1024
AVATAR_SIZE = 40  # pixel size for avatars in the Active Users list
COMPOSE_BG = "#ffffff"  # background of the unified compose bar (white)
RIGHT_MARGIN = 10  # px gap between controls group and right edge of the white bar
DEBUG = False  # Toggle verbose debug logs

def dprint(*args, **kwargs):
    if DEBUG:
        try:
            print(*args, **kwargs)
        except Exception:
            pass

def create_circular_avatar(avatar_path: str, size: int = 50, master: Optional[tk.Misc] = None) -> Optional[ImageTk.PhotoImage]:
    """Create a circular-cropped PhotoImage from avatar_path. Returns None on failure."""
    try:
        # Choose a resampling filter compatible with various Pillow versions
        try:
            resample = Image.Resampling.LANCZOS  # Pillow >= 9.1
        except Exception:
            resample = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", Image.BICUBIC))

        # Load image and resize
        img = Image.open(avatar_path).convert("RGBA")
        img = img.resize((size, size), resample)

        # Create circular mask
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)

        # Apply mask
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(img, (0, 0))
        output.putalpha(mask)
        return ImageTk.PhotoImage(output, master=master)
    except Exception as e:
        dprint(f"Avatar load error for '{avatar_path}': {e}")
        return None

def resolve_avatar_path(base_dir: str, avatar_path: Optional[str]) -> Optional[str]:
    """Resolve avatar path to an existing file (absolute, relative, or client/img)."""
    if not avatar_path or str(avatar_path) == "None":
        return None
    candidate = str(avatar_path).strip()
    # Case 1: absolute path
    if os.path.isabs(candidate) and os.path.exists(candidate):
        return candidate
    # Case 2: relative to client/ (may include 'img/')
    joined = os.path.join(base_dir, candidate)
    if os.path.exists(joined):
        return joined
    # Case 3: just a filename under client/img
    joined2 = os.path.join(base_dir, "img", os.path.basename(candidate))
    if os.path.exists(joined2):
        return joined2
    dprint(f"Avatar not found for '{avatar_path}' (checked relative and client/img)")
    return None

def load_icon_photo(base_dir: str, rel_path: str, size: int, master: tk.Misc) -> Optional[ImageTk.PhotoImage]:
    """Load an icon from a PNG file and return PhotoImage. Returns None if missing."""
    path = os.path.join(base_dir, rel_path)
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        try:
            resample = Image.Resampling.LANCZOS
        except Exception:
            resample = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", Image.BICUBIC))
        img = img.resize((size, size), resample)
        return ImageTk.PhotoImage(img, master=master)
    except Exception as e:
        dprint(f"load_icon_photo failed for {path}: {e}")
        return None

class ChatUI(tk.Tk):
    def __init__(self, username: str, net):
        super().__init__()
        # ===== Window and layout =====
        self.title("FUV Chatroom")
        self.geometry("900x600")
        self.username = username
        self.net = net
        self.net.on_message = self._on_message   # set the callback for incoming messages
        # Cache own avatar filename if provided by NetClient
        self.my_avatar = getattr(self.net, "avatar", None)

        # right pane / user list
        # Target 80/20 split between chat (col 0) and Active (col 1)
        self.columnconfigure(0, weight=4, uniform="cols")  # main chat area wider (≈80%)
        self.columnconfigure(1, weight=1, uniform="cols", minsize=80)  # Active (≈20%) with a small minimum
        self.rowconfigure(1, weight=1)

        header = tk.Label(self, text="FUV Chatroom", bg="#a1ecf7", font=("Segoe UI", 16, "bold"))
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

    # ===== Active Users (avatar list) =====
        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(4,8))
        ttk.Label(right, text="Active Users", background="#a1ecf7", font=("Segoe UI", 10, "bold")).pack(fill="x")
        
        # Create canvas for custom user list with avatars
        self.user_canvas = tk.Canvas(right, bg="white", highlightthickness=0)
        user_scroll = ttk.Scrollbar(right, orient="vertical", command=self.user_canvas.yview)
        self.user_frame = ttk.Frame(self.user_canvas)
        
        self.user_canvas.configure(yscrollcommand=user_scroll.set)
        self.user_canvas.pack(side="left", fill="both", expand=True, pady=2)
        user_scroll.pack(side="right", fill="y")
        
        self.user_canvas.create_window((0, 0), window=self.user_frame, anchor="nw")
        self.user_frame.bind("<Configure>", lambda e: self.user_canvas.configure(scrollregion=self.user_canvas.bbox("all")))
        
        # Store user data: {username: {"avatar": path, "widget": frame, "photo": PhotoImage}}
        self.user_data = {}
        self.selected_user = None  # Currently selected user for private messaging
        self._avatar_cache = {}    # Keep strong references to PhotoImages
        # Show self immediately as a fallback until server's userlist arrives
        try:
            self.update_user_list({self.username: self.my_avatar})
        except Exception:
            pass

    # ===== Unified compose area (rounded input with inline controls) =====
        base_dir = os.path.dirname(__file__)
        self.compose_canvas = tk.Canvas(self, height=46, bg=self["bg"], highlightthickness=0)
        self.compose_canvas.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=8)

        # Enforce proportional split on resize using minsizes
        self._split_ratio = (4, 1)
        self._active_min = 100
        def _apply_split(_=None):
            try:
                total = sum(self._split_ratio)
                w = max(0, self.winfo_width() - 16)  # account for borders/margins
                if w <= 0:
                    return
                right = max(self._active_min, int(w * self._split_ratio[1] / total))
                left = max(200, w - right)
                self.columnconfigure(0, minsize=left)
                self.columnconfigure(1, minsize=right)
            except Exception:
                pass
        self.bind("<Configure>", _apply_split)
        self.after(0, _apply_split)

        # Internal widgets: a container frame inside the canvas so controls can be grouped on the right
        self.compose_inner = tk.Frame(self.compose_canvas, bg=COMPOSE_BG, highlightthickness=0, bd=0)
        self._compose_win_id = self.compose_canvas.create_window(0, 0, anchor="nw", window=self.compose_inner)

        # Left: expanding Entry
        self.entry = tk.Entry(self.compose_inner, bd=0, bg=COMPOSE_BG, highlightthickness=0, relief="flat")
        self.entry.bind("<Return>", lambda e: self.send_text())
        self.entry.pack(side="left", fill="x", expand=True, padx=(12, 0), pady=8, ipady=3)

        # Right: controls group (file, emoji, send)
        controls = tk.Frame(self.compose_inner, bg=COMPOSE_BG, highlightthickness=0, bd=0)
        controls.pack(side="right", padx=(0, RIGHT_MARGIN), pady=6)

        self.file_icon = load_icon_photo(base_dir, os.path.join("img", "file_button.png"), size=20, master=self)
        self.file_lbl = tk.Label(controls, image=self.file_icon, bg=COMPOSE_BG, cursor="hand2")
        self.file_lbl.image = self.file_icon
        self.file_lbl.pack(side="left", padx=(0, 8))
        self.file_lbl.bind("<Button-1>", lambda e: self.send_file())

        self.emoji_icon = load_icon_photo(base_dir, os.path.join("img", "emoji_button.png"), size=20, master=self)
        self.emoji_lbl = tk.Label(controls, image=self.emoji_icon, bg=COMPOSE_BG, cursor="hand2")
        self.emoji_lbl.image = self.emoji_icon
        self.emoji_lbl.pack(side="left", padx=(0, 8))
        self.emoji_lbl.bind("<Button-1>", lambda e: self.open_emoji_picker())

        self.send_btn = tk.Button(controls, text="Send", command=self.send_text,
                                  bg="#7C3AED", fg="white", activebackground="#6D28D9", activeforeground="white",
                                  bd=0, relief="flat", cursor="hand2", padx=12, pady=4, highlightthickness=0)
        self.send_btn.pack(side="left")

        # Placeholder behavior
        self._placeholder_text = "Type your message..."
        self._placeholder_active = False
        def _apply_placeholder():
            if not self.entry.get():
                self.entry.insert(0, self._placeholder_text)
                self.entry.config(fg="#888888")
                self._placeholder_active = True
        def _remove_placeholder(_=None):
            if self._placeholder_active:
                self.entry.delete(0, "end")
                self.entry.config(fg="#000000")
                self._placeholder_active = False
        self.entry.bind("<FocusIn>", _remove_placeholder)
        def _on_focus_out(_):
            if not self.entry.get().strip():
                _apply_placeholder()
        self.entry.bind("<FocusOut>", _on_focus_out)
        _apply_placeholder()

        # Draw a rounded background and lay out widgets responsively
        self._compose_bg_items = []
        def _clear_bg():
            for it in self._compose_bg_items:
                try:
                    self.compose_canvas.delete(it)
                except Exception:
                    pass
            self._compose_bg_items.clear()

        def _draw_rounded_rect(x1, y1, x2, y2, r, fill):
            # four corner arcs
            self._compose_bg_items.append(self.compose_canvas.create_arc(x1, y1, x1+2*r, y1+2*r, start=90, extent=90, outline="", fill=fill))
            self._compose_bg_items.append(self.compose_canvas.create_arc(x2-2*r, y1, x2, y1+2*r, start=0, extent=90, outline="", fill=fill))
            self._compose_bg_items.append(self.compose_canvas.create_arc(x1, y2-2*r, x1+2*r, y2, start=180, extent=90, outline="", fill=fill))
            self._compose_bg_items.append(self.compose_canvas.create_arc(x2-2*r, y2-2*r, x2, y2, start=270, extent=90, outline="", fill=fill))
            # center rectangles
            self._compose_bg_items.append(self.compose_canvas.create_rectangle(x1+r, y1, x2-r, y2, outline="", fill=fill))
            self._compose_bg_items.append(self.compose_canvas.create_rectangle(x1, y1+r, x2, y2-r, outline="", fill=fill))

        def _relayout(e=None):
            w = self.compose_canvas.winfo_width()
            h = self.compose_canvas.winfo_height()
            if w <= 1:
                return
            pad = 10
            r = 16
            # redraw background
            _clear_bg()
            _draw_rounded_rect(pad, 4, w-pad, h-4, r, COMPOSE_BG)
            # position and size the inner frame (with a small inset)
            try:
                self.compose_canvas.coords(self._compose_win_id, pad, 4)
                self.compose_canvas.itemconfigure(self._compose_win_id, width=w - 2*pad, height=h - 8)
            except Exception:
                pass

        self.compose_canvas.bind("<Configure>", _relayout)
        # Initial layout once the window is visible
        self.after(0, _relayout)

        # Prefer a font with colored emoji on Windows
        try:
            emoji_font = ("Segoe UI Emoji", 11)
            self.entry.configure(font=emoji_font)
            self.text.configure(font=emoji_font)
        except Exception:
            pass

        # file_id -> {"name":..., "chunks":{}}
        self.current_downloads = {}
        # {"path": str} during an active upload
        self.current_upload = None

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

    def ts(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def update_user_list(self, users_dict: Dict[str, Optional[str]]):
        """Update the Active Users list with avatars. users_dict: {username: avatar_path}"""
        # Merge with existing/self avatar if incoming dict lacks it
        prev = dict(self.user_data)
        merged: Dict[str, Optional[str]] = {}
        for uname, av in users_dict.items():
            chosen = av
            # If server sent no avatar, prefer previous known one
            if (chosen is None or str(chosen) == "None"):
                if uname == self.username and self.my_avatar:
                    chosen = self.my_avatar
                elif uname in prev and prev[uname].get("avatar") and str(prev[uname]["avatar"]) != "None":
                    chosen = prev[uname]["avatar"]
            merged[uname] = chosen

        dprint(f"DEBUG: update_user_list merged={merged}")

        # Clear existing widgets
        for widget in self.user_frame.winfo_children():
            widget.destroy()
        self.user_data.clear()
        
        # Add each user with avatar
        for username, avatar_path in merged.items():
            user_frame = tk.Frame(self.user_frame, bg="white", cursor="hand2")
            user_frame.pack(fill="x", padx=4, pady=2)
            
            # Load avatar image (circular)
            photo = None
            base_dir = os.path.dirname(__file__)
            img_path = resolve_avatar_path(base_dir, avatar_path)
            dprint(f"DEBUG: resolve avatar for '{username}': requested='{avatar_path}', resolved='{img_path}'")
            if img_path:
                photo = create_circular_avatar(img_path, size=AVATAR_SIZE, master=self)
            
            # Create avatar label (or placeholder if no image)
            if photo:
                avatar_label = tk.Label(user_frame, image=photo, bg="white", borderwidth=0)
                # Keep references to prevent garbage collection
                avatar_label.image = photo
                self._avatar_cache[username] = photo
            else:
                # Fallback: show first letter of username in a circular background
                canvas = tk.Canvas(user_frame, width=40, height=40, bg="white", highlightthickness=0)
                canvas.create_oval(2, 2, 38, 38, fill="#cccccc", outline="")
                canvas.create_text(20, 20, text=username[0].upper(), 
                                  fill="white", font=("Segoe UI", 16, "bold"))
                avatar_label = canvas
            avatar_label.pack(side="left", padx=(4, 8))

            # Username label with better styling
            name_label = tk.Label(user_frame, text=username, bg="white", 
                                 font=("Segoe UI", 12), anchor="w", fg="#333333")
            name_label.pack(side="left", fill="x", expand=True, pady=4)
            
            # Store user data
            self.user_data[username] = {
                "avatar": avatar_path,
                "widget": user_frame,
                "photo": photo
            }
            
            # Bind click to select user
            def make_select_handler(uname, frame):
                def handler(e=None):
                    self._select_user(uname, frame)
                return handler
            
            user_frame.bind("<Button-1>", make_select_handler(username, user_frame))
            avatar_label.bind("<Button-1>", make_select_handler(username, user_frame))
            name_label.bind("<Button-1>", make_select_handler(username, user_frame))
    
    def _select_user(self, username: str, frame: tk.Frame):
        """Select a user for private messaging"""
        # Clear previous selection
        for data in self.user_data.values():
            data["widget"].config(bg="white")
            for child in data["widget"].winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg="white")
        
        # Highlight selected user
        frame.config(bg="#e3f2fd")
        for child in frame.winfo_children():
            if isinstance(child, tk.Label):
                child.config(bg="#e3f2fd")
        
        self.selected_user = username

    def send_text(self):
        # Treat placeholder as empty
        txt = self.entry.get()
        raw = "" if getattr(self, "_placeholder_active", False) or txt == self._placeholder_text else txt.strip()
        if not raw:
            return
        self.entry.delete(0, "end")
        # Re-apply placeholder after sending
        try:
            if hasattr(self, "_placeholder_active"):
                self._placeholder_active = False
                if not self.entry.get():
                    self.entry.event_generate("<FocusOut>")
        except Exception:
            pass

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
            if self.selected_user == self.username:
                self.append("(System) You cannot private-message yourself.", "system")
                return
            msg = emoji.emojize(raw, language="alias")
            self.net.send_private(self.selected_user, msg)
            self.append(f"(Private) (To {self.selected_user}) ({self.ts()}): {msg}", "private")
        else:
            msg = emoji.emojize(raw, language="alias")
            self.net.send_public(msg)

    # ========== Emoji picker UI ==========
    def open_emoji_picker(self):
        # Prevent multiple windows
        if getattr(self, "_emoji_win", None) and tk.Toplevel.winfo_exists(self._emoji_win):
            self._emoji_win.lift()
            return

        win = tk.Toplevel(self)
        self._emoji_win = win
        win.title("Pick an emoji")
        win.transient(self)
        win.resizable(False, False)
        # Position near the emoji button
        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            win.geometry(f"360x280+{x-190}+{y-350}")
        except Exception:
            win.geometry("360x280")

        # Close on focus loss or Escape
        win.bind("<Escape>", lambda e: win.destroy())

        # Remember caret position so we can insert at the right place
        try:
            self._emoji_insert_pos = self.entry.index("insert")
        except Exception:
            self._emoji_insert_pos = None

        # Search bar
        top = ttk.Frame(win)
        top.pack(fill="x", padx=8, pady=(8,4))
        ttk.Label(top, text="Search:").pack(side="left")
        query = tk.StringVar(master=win)
        ent = ttk.Entry(top, textvariable=query)
        ent.pack(side="left", fill="x", expand=True, padx=(6,0))

        # Scrollable canvas for grid
        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=8, pady=(0,8))
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame = ttk.Frame(canvas)
        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Embed the frame and keep the window id so we can resize it with the canvas
        window_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Keep the embedded frame width in sync with the canvas width to avoid
        # horizontal clipping and to make the vertical scrollbar reliable.
        def _on_canvas_config(e):
            try:
                canvas.itemconfigure(window_id, width=e.width)
            except Exception:
                pass

        canvas.bind("<Configure>", _on_canvas_config)

    # Mouse-wheel scrolling: bind when pointer enters the canvas, unbind on leave
        def _on_mousewheel(event):
            try:
                if hasattr(event, 'delta') and event.delta:
                    # Windows/macOS
                    step = -1 * int(event.delta / 120)
                    canvas.yview_scroll(step, 'units')
                elif hasattr(event, 'num'):
                    # X11: Button-4 (up), Button-5 (down)
                    if event.num == 4:
                        canvas.yview_scroll(-1, 'units')
                    elif event.num == 5:
                        canvas.yview_scroll(1, 'units')
            except Exception:
                pass

        def _bind_mousewheel(_e):
            if sys.platform.startswith('linux'):
                canvas.bind_all('<Button-4>', _on_mousewheel)
                canvas.bind_all('<Button-5>', _on_mousewheel)
            else:
                canvas.bind_all('<MouseWheel>', _on_mousewheel)

        def _unbind_mousewheel(_e):
            if sys.platform.startswith('linux'):
                canvas.unbind_all('<Button-4>')
                canvas.unbind_all('<Button-5>')
            else:
                canvas.unbind_all('<MouseWheel>')

        canvas.bind('<Enter>', _bind_mousewheel)
        canvas.bind('<Leave>', _unbind_mousewheel)

        # Build emoji buttons
        style = ttk.Style(win)
        try:
            style.configure("Emoji.TButton", font=("Segoe UI Emoji", 16), padding=(4, 2))
        except Exception:
            style.configure("Emoji.TButton", padding=(4, 2))
        all_items = self._emoji_items()

        def render(items):
            for child in frame.winfo_children():
                child.destroy()
            cols = 7
            r = c = 0
            for sym, code in items:
                btn = ttk.Button(frame, text=sym, width=3, style="Emoji.TButton")
                # Insert the actual symbol to avoid alias issues, then close the window
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
            q = query.get().strip().lower()
            if not q:
                render(all_items)
                return
            filtered = [it for it in all_items if q in it[1].strip(":").replace("_", " ")]
            render(filtered)

        query.trace_add("write", lambda *_: do_filter())
        render(all_items)
        ent.focus_set()

    def _insert_symbol(self, symbol: str):
        try:
            # Focus the entry and process focus-in to clear placeholder if needed
            self.entry.focus_set()
            try:
                self.entry.update_idletasks()
            except Exception:
                pass
            # If placeholder is active or text equals placeholder, clear it
            try:
                if getattr(self, "_placeholder_active", False) or self.entry.get() == getattr(self, "_placeholder_text", ""):
                    self.entry.delete(0, "end")
                    try:
                        self.entry.config(fg="#000000")
                    except Exception:
                        pass
                    self._placeholder_active = False
            except Exception:
                pass

            # Place cursor where user left it when opening the picker; default to end
            pos = getattr(self, "_emoji_insert_pos", None)
            try:
                self.entry.icursor(pos if pos is not None else "end")
            except Exception:
                try:
                    self.entry.icursor("end")
                except Exception:
                    pass
            # Insert symbol
            self.entry.insert("insert", symbol)
        except Exception:
            # Fallback to appending
            try:
                self.entry.insert("end", symbol)
            except Exception:
                pass

    def _emoji_items(self):
        # Common set covering many reactions. Shown symbol + alias for textual search
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
                items.append((emoji.emojize(c, language="alias"), c))
            except Exception:
                # If emojize fails for some alias, skip it silently
                dprint(f"Emoji emojize failed for alias {c}")
        return items

    def send_file(self):
        broadcast = False
        to_user = None
        if not self.selected_user:
            # No recipient selected → broadcast to everyone without prompting
            broadcast = True
        else:
            to_user = self.selected_user
            if to_user == self.username:
                messagebox.showinfo("Invalid", "Choose another user.")
                return
        path = filedialog.askopenfilename()
        if not path:
            return
        size = os.path.getsize(path)
        if broadcast:
            self.net.send_file_offer("*", path, size)
            self.append(f"(System) ({self.ts()}) Offered file '{os.path.basename(path)}' to everyone.", "system")
        else:
            self.net.send_file_offer(to_user, path, size)
            self.append(f"(System) ({self.ts()}) Offered file '{os.path.basename(path)}' to {to_user}.", "system")

        # Wait for ACK in _on_message; if accepted, stream chunks
        self.current_upload = {"path": path}

    # ========== Incoming messages ==========
    def _on_message(self, env: Dict[str, Any]):
        t = env.get("type")
        if t == "system":
            self.append(f"(System) {env['payload'].get('text','')}", "system")
            return
        if t == "userlist":
            users_payload = env.get("payload", {}).get("users", {})
            # Accept both formats: list of usernames OR dict {username: avatar}
            if isinstance(users_payload, dict):
                users_dict = users_payload
            elif isinstance(users_payload, list):
                users_dict = {u: None for u in users_payload}
            else:
                users_dict = {}

            dprint(f"DEBUG: Received userlist: {users_dict}")
            # Marshal UI update to Tk main thread
            try:
                self.after(0, lambda d=users_dict: self.update_user_list(d))
            except Exception:
                # Fallback to direct call (may be unsafe across threads)
                self.update_user_list(users_dict)
            return

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
            name, size = body["name"], body["size"]
            if messagebox.askyesno("File transfer", f"{env['sender']} wants to send you '{name}' ({size} bytes). Accept?"):
                file_id = str(uuid.uuid4())
                self.net.send_file_ack(env["sender"], file_id, True)
                self.current_downloads[file_id] = {"name": name, "chunks": {}, "next": 0}
                self.append(f"(System) Accepted file '{name}' from {env['sender']}", "system")
            else:
                self.net.send_file_ack(env["sender"], "", False)
        elif t == "file_ack":
            if not body.get("accept"):
                self.append(f"(System) {env['sender']} declined your file.", "system")
            else:
                # start upload to the ACK sender (works for direct or broadcast offers)
                if not self.current_upload:
                    return
                fid = body["id"]
                path = self.current_upload["path"]
                to_user = env["sender"]
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
                self.append(f"(System) Finished sending '{os.path.basename(path)}'", "system")
        elif t == "file_chunk":
            fid, seq, final = body["id"], body["seq"], body["final"]
            ch = body["data"].encode("latin1")
            ctx = self.current_downloads.get(fid)
            if not ctx:
                # first chunk without offer? initialize
                self.current_downloads[fid] = ctx = {"name":"file.bin","chunks":{}, "next":0}
            ctx["chunks"][seq] = ch
            if final:
                # reconstruct in order
                ordered = bytearray()
                for i in range(len(ctx["chunks"])):
                    ordered.extend(ctx["chunks"][i])
                save = filedialog.asksaveasfilename(defaultextension="",
                                                    initialfile=ctx["name"])
                if save:
                    with open(save, "wb") as f:
                        f.write(ordered)
                    self.append(f"(System) Saved file to {save}", "system")
                else:
                    self.append("(System) File save was canceled.", "system")

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