import json
import socket

ENC = "utf-8"   # encoding for JSON text
DELIM = b"\n"    # delimiter for JSON text

_buffers: dict[int, bytearray] = {}   # buffer to store residual bytes per socket
# message per call even when multiple messages arrive in one recv().

def send_json(sock: socket.socket, obj: dict) -> None:
    '''
    The function sends an object that can be converted to JSON over a socket. 
    It adds a newline character \n at the end of the message
    Input:
        - sock: socket.socket - the socket to send the data through
        - obj: dict - the object to be sent
    Output: None
    '''
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode(ENC) 
    sock.sendall(data)

def recv_json(sock: socket.socket) -> dict:
    '''
    Receive exactly one newline-delimited JSON object from the socket.
    Handles the case where multiple JSON messages arrive in a single recv()
    by using a buffer to store residual bytes for each socket.
    '''
    fd = sock.fileno()   # get the file descriptor of the socket ( it is an integer)
    buf = _buffers.setdefault(fd, bytearray())

    while True:
        # Check if we have a complete line in the buffer
        nl = buf.find(DELIM)
        if nl != -1:  # found a newline
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
