import json
import socket

ENC = "utf-8"   # encoding for JSON text
DELIM = b"\n"    # delimiter for JSON text



_buffers: dict[int, bytearray] = {}   # buffer to store residual bytes per socket
# message per call even when multiple messages arrive in one recv().

def send_json(sock: socket.socket, obj: dict) -> None:
    '''
    This function sends a JSON-serializable object over a socket, 
    appending a newline as a delimiter.
    '''
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode(ENC) 
    sock.sendall(data)

def recv_json(sock: socket.socket) -> dict:
    '''
    Receive exactly one newline-delimited JSON object from the socket.
    Handles the case where multiple JSON messages arrive in a single recv()
    by buffering residual bytes per socket.
    '''
    fd = sock.fileno()
    buf = _buffers.setdefault(fd, bytearray())

    while True:
        # If we already have a full line in the buffer, use it first
        nl = buf.find(DELIM)
        if nl != -1:
            line_bytes = buf[:nl]
            del buf[:nl+1]
            line = line_bytes.decode(ENC)
            return json.loads(line)

        # Otherwise, read more from the socket
        chunk = sock.recv(4096)
        if not chunk:
            # Socket closed
            raise ConnectionError("socket closed")
        buf.extend(chunk)
