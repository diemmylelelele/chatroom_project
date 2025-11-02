"""
Main entry point for chatroom client.
Display login window first, then connect and open chat UI.
"""
import argparse
from .net import NetClient, DuplicateUsernameError
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

    # Step 1(+2 pre-check): Loop login until we can connect without duplicate username
    error_msg = None
    while True:
        username, avatar_id = show_login(error_message=error_msg)
        # If user closes login window (no login), exit program
        if username is None:
            print("Login cancelled. Exiting program.")
            return

        # Try to connect using provided username
        # Don't attach a handler yet - let messages backlog until UI is created
        net = NetClient(args.host, args.port, username, on_message=None, avatar_id=avatar_id)
        try:
            net.connect()
            break
        except DuplicateUsernameError:
            # Show error message inline and let user retry
            error_msg = "Username already exists. Please try another one."
            continue

    print(f"Connected as user: {username}, avatar: {avatar_id + 1}")

    # Step 3: Create UI after successful connection
    ui = ChatUI(username, net, avatar_id)
    
    # Setup window close handler
    ui.protocol("WM_DELETE_WINDOW", lambda: (net.close(), ui.destroy()))
    
    # Start UI main loop
    ui.mainloop()


if __name__ == "__main__":
    main()
