import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime, os, uuid
import emoji
from typing import Dict, Any, Optional

from common.crypto import decrypt_body

CHUNK = 32 * 1024 

class ChatUI(tk.Tk):
    def __init__(self, username: str, net):
        super().__init__()
        self.title("FUV Chatroom")
        self.geometry("900x600")
        self.username = username
        self.net = net
        self.net.on_message = self._on_message   # set the callback for incoming messages

        # right pane / user list
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=1)
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

        # user list
        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(4,8))
        ttk.Label(right, text="Active", background="#a1ecf7").pack(fill="x")
        self.users = tk.Listbox(right)
        self.users.pack(fill="both", expand=True, pady=4)

        # compose area
        compose = ttk.Frame(self)
        compose.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        compose.columnconfigure(0, weight=1)

        self.entry = ttk.Entry(compose)
        self.entry.grid(row=0, column=0, sticky="ew", ipady=6)
        self.entry.bind("<Return>", lambda e: self.send_text())

        ttk.Button(compose, text="😊", width=8, command=self.insert_emoji).grid(row=0, column=1, padx=4)
        ttk.Button(compose, text="📎", width=8, command=self.send_file).grid(row=0, column=2, padx=4)
        ttk.Button(compose, text="Send ➤", command=self.send_text).grid(row=0, column=3, padx=4)

        self.current_downloads: Dict[str, dict] = {}  # file_id -> {"name":..., "chunks":{}}
        self.current_upload: Optional[dict] = None    # {"path": str}

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
        selection = self.users.curselection()
        if selection:
            target = self.users.get(selection[0])
            if target == self.username:
                self.append("(System) You cannot private-message yourself.", "system")
                return
            msg = emoji.emojize(raw, language="alias")
            self.net.send_private(target, msg)
            self.append(f"(Private) (To {target}) ({self.ts()}): {msg}", "private")
        else:
            msg = emoji.emojize(raw, language="alias")
            self.net.send_public(msg)

    def insert_emoji(self):
        # minimal picker: insert a common emoji code
        codes = [":smile:", ":heart:", ":thumbs_up:", ":grinning:", ":clap:", ":rocket:"]
        menu = tk.Menu(self, tearoff=0)
        for c in codes:
            menu.add_command(label=f"{emoji.emojize(c)}  {c}", command=lambda cc=c: self._ins(cc))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _ins(self, code: str):
        self.entry.insert("insert", code)

    def send_file(self):
        selection = self.users.curselection()
        broadcast = False
        to_user = None
        if not selection:
            # No recipient selected → broadcast to everyone without prompting
            broadcast = True
        else:
            to_user = self.users.get(selection[0])
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

    # --------- incoming messages ----------
    def _on_message(self, env: Dict[str, Any]):
        t = env.get("type")
        if t == "system":
            self.append(f"(System) {env['payload'].get('text','')}", "system")
            return
        if t == "userlist":
            users = env["payload"]["users"]
            self.users.delete(0, "end")
            for u in users:
                self.users.insert("end", u)
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
