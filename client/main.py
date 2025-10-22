"""
Main entry point for chatroom client.
Display login window first, then connect and open chat UI.
"""
import argparse
from .net import NetClient
from .ui import ChatUI
from .login import show_login


def main():
    """
    Start chatroom client.
    
    Step 1: Display login window for user to enter name and choose avatar
    Step 2: Connect to server with login information
    Step 3: Open chat UI
    """
    # Parse command line arguments (host and port)
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="Server host address")
    ap.add_argument("--port", type=int, default=5050, help="Server port")
    args = ap.parse_args()

    # Step 1: Display login window
    username, avatar_id = show_login()
    
    # If user closes login window (no login), exit program
    if username is None:
        print("Login cancelled. Exiting program.")
        return

    print(f"Login successful with user: {username}, avatar: {avatar_id + 1}")

    # Step 2 & 3: Create NetClient and ChatUI, then connect
    # Create UI first so it can register the on_message handler before connecting
    dummy = lambda e: None
    net = NetClient(args.host, args.port, username, on_message=dummy, avatar_id=avatar_id)
    ui = ChatUI(username, net, avatar_id)
    
    # Connect to server
    net.connect()
    
    # Setup window close handler
    ui.protocol("WM_DELETE_WINDOW", lambda: (net.close(), ui.destroy()))
    
    # Start UI main loop
    ui.mainloop()


if __name__ == "__main__":
    main()
