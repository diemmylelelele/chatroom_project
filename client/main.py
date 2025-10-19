import argparse
from .net import NetClient
from .ui import ChatUI
from .login import LoginWindow

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5050)
    # Remove --user; now collected from login UI
    args = ap.parse_args()

    # Store selected username and avatar from login
    user_data = {"username": None, "avatar": None}

    def on_login_attempt(username: str, avatar: str):
        """
        Called when user clicks Login button.
        Try to connect to server; if duplicate username, show error and stay on login.
        Otherwise, close login and open chat UI.
        """
        user_data["username"] = username
        user_data["avatar"] = avatar

        # Create NetClient with dummy callback first (will be replaced by ChatUI)
        dummy = lambda e: None
        net = NetClient(args.host, args.port, username, on_message=dummy, avatar=avatar)
        
        # Create ChatUI BEFORE connecting, so it can register the real on_message handler
        ui = ChatUI(username, net)
        ui.title(f"FUV Chatroom - {username} {avatar}")
        
        try:
            # Now connect - the recv_loop will use ui's on_message handler
            net.connect()
            # Success: close login window and show chat UI
            login_win.withdraw()  # hide login
            login_win.destroy()  # destroy login window
            ui.protocol("WM_DELETE_WINDOW", lambda: (net.close(), ui.destroy()))
            ui.mainloop()
        except ConnectionRefusedError as e:
            # Server rejected (likely duplicate username)
            ui.destroy()  # destroy the UI we just created
            if "DUPLICATE_USERNAME" in str(e):
                login_win.deiconify()  # show login again
                login_win.show_duplicate_error()
            else:
                # Other connection error
                login_win.deiconify()
                login_win.show_duplicate_error()  # reuse for now, or make generic error
            # Keep login window open for retry
        except Exception as e:
            # Network or other error
            ui.destroy()  # destroy UI
            from tkinter import messagebox
            messagebox.showerror("Connection Error", f"Could not connect to server:\n{e}")
            login_win.destroy()

    # Show login window first
    login_win = LoginWindow(on_login=on_login_attempt)
    login_win.mainloop()

if __name__ == "__main__":
    main()
