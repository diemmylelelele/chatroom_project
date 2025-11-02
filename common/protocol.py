import json
import socket

ENC = "utf-8"   # encoding for JSON text
DELIM = b"\n"    # delimiter for JSON text

_buffers: dict[int, bytearray] = {}   # buffers(key: socket ID, value: bytearray) to store residual data
# message per call even when multiple messages arrive in one recv().

def send_json(sock: socket.socket, obj: dict) -> None:
    '''
    The function sends an object that can be converted to JSON over a socket. 
    It adds a newline character \n at the end of the message
    Inputs:
        - sock: socket.socket - the socket to send the data through
        - obj: dict - the object to be sent
    Output: None
    '''
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode(ENC) # encode the object to bytes
    sock.sendall(data)   # send all data(bytes) through the socket

def recv_json(sock: socket.socket) -> dict:
    '''
    The function receives a JSON object from a socket. It reads data until it encounters a newline character \n,
    which indicates the end of the JSON message. Then it decodes the bytes to text and converts it to a JSON object.
    Input:
        - sock: socket.socket - the socket to receive data from
    Output:
        - dict - the received JSON object         
    '''
    fd = sock.fileno()   # get unique identifier (int ID) for this socket
    buf = _buffers.setdefault(fd, bytearray())  # get the existing buffer or create  new buffer for this socket

    while True:
        # Check if we have a complete line in the buffer
        nl = buf.find(DELIM)
        if nl != -1:  # If new line found, that means one full JSON message has arrived.
            line_bytes = buf[:nl]  # extract that line bytes
            del buf[:nl+1]         # remove that line and delimiter from the buffer
            line = line_bytes.decode(ENC)   # decode that bytes to text
            return json.loads(line)         

        # Otherwise, read more from the socket
        chunk = sock.recv(4096)   # read more bytes from the socket
        if not chunk:
            # Socket closed
            raise ConnectionError("socket closed")
        buf.extend(chunk)  # append the newly received bytes to the buffer
