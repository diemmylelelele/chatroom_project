import argparse
from .net import NetClient
from .ui import ChatUI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5050)
    ap.add_argument("--user", required=True)
    args = ap.parse_args()

    # create UI first so it can register the on_message handler before connecting
    dummy = lambda e: None
    net = NetClient(args.host, args.port, args.user, on_message=dummy)
    ui = ChatUI(args.user, net)
    net.connect()
    ui.protocol("WM_DELETE_WINDOW", lambda: (net.close(), ui.destroy()))
    ui.mainloop()

if __name__ == "__main__":
    main()
