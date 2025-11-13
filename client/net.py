import socket, threading, datetime, json, os
from queue import Queue
from typing import Optional, Callable, Dict, Any, List

from common.protocol import send_json, recv_json
from common.crypto import aes_key, rsa_wrap_key, encrypt_body, decrypt_body

ENC = "utf-8"


class DuplicateUsernameError(Exception):
    """Raised when the server rejects an auth because the username is already in use."""
    pass

class NetClient:
    ''' Network client for chat application '''
    def __init__(self, host: str, port: int, username: str,
                 on_message: Optional[Callable[[Dict[str,Any]], None]] = None,
                 avatar_id: int = 0):
        self.host, self.port, self.username = host, port, username
        self.avatar_id = avatar_id  # User's avatar ID (0-1)
        self.sock: Optional[socket.socket] = None
        # Backlog messages until UI attaches the handler; then flush
        self._on_message: Optional[Callable[[Dict[str,Any]], None]] = None   # when a message is received, this function will be called
        self._backlog: List[Dict[str,Any]] = []   # store message received before UI attaches
        if on_message:
            self.on_message = on_message
        self.session_key: Optional[bytes] = None   # AES session key after key-exchange
        self.recv_thread: Optional[threading.Thread] = None   # thread for receiving messages
        self.running = False

    @property
    def on_message(self) -> Optional[Callable[[Dict[str,Any]], None]]:
        ''' The callback function for handling incoming messages '''
        return self._on_message

    @on_message.setter   
    def on_message(self, cb: Optional[Callable[[Dict[str,Any]], None]]):
        '''
        Set the callback for incoming messages. If there are any backlog messages received before
        the UI attached, flush them now.
        Input:
            - cb: callback function that accepts a message environment dict
        '''
        self._on_message = cb
        # Flush any messages received before the UI attached
        if cb and self._backlog:  # If there are pending messages, replay them
            pending = self._backlog # make copy of temporary backlog( including old messages )
            self._backlog = [] # clear the main backlog immediately to avoid duplication
            for env in pending:  # loop through the pending (including old messages) 
                try:
                    cb(env)   # call newly provided function for each pending(old) message
                except Exception:
                    # Ignore UI errors to avoid breaking network thread
                    pass

    def iso_now(self):
        return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def connect(self):
        # Establish a TCP connection to the chat server.
        self.sock = socket.create_connection((self.host, self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Disable Nagle's algorithm: send any data immediately
        # Send auth with avatar_id and username to server
        send_json(self.sock, {"type":"auth","sender":None,"to":None,"ts":self.iso_now(),
                              "payload":{"username": self.username, "avatar_id": self.avatar_id}})
        # Receive first response (could be RSA pub or an error) from server
        env = recv_json(self.sock)  
        # Handle duplicate username gracefully so caller can show inline error
        if env.get("type") == "error":
            code = (env.get("payload") or {}).get("code")
            try:
                # Close the temp socket so the client can retry cleanly
                if self.sock:
                    self.sock.close()
            finally:
                self.sock = None
            if code == "DUPLICATE_USERNAME":  # if the username is already taken
                raise DuplicateUsernameError("Username already exists")
            else:
                raise RuntimeError(f"Server error: {code}")
        # Expecting server's RSA public key
        server_pub = env["payload"]["server_pub_pem"] # get user's RSA public key in PEM format
        # Generate AES key
        self.session_key = aes_key()
        # Encrypt the session AES key with server's RSA public key
        wrapped = rsa_wrap_key(server_pub, self.session_key)
        # Start listening for incoming messages BEFORE sending wrapped key
        # so we catch the immediate "joined" system notification and userlist
        self.running = True
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()
        # Send wrapped encrypted AES key to server ( including AES session key )
        send_json(self.sock, {"type":"key","sender":self.username,"to":None,"ts":self.iso_now(),
                              "payload":{"wrapped": wrapped}})

    def close(self):
        try:
            if self.sock: # if socket exists
                send_json(self.sock, {"type":"system","sender":self.username,"to":None,"ts":self.iso_now(),
                                      "payload":{"event":"leave"}})   # notify server we are leaving
        except Exception:
            pass
        self.running = False
        try:
            if self.sock: self.sock.close()
        except Exception:
            pass


    def send_public(self, text: str):
        ''' Send a public message to all users '''
        body = {"text": text}
        env = {"type":"pub","sender":self.username,"to":"*","ts":self.iso_now(),
               "payload": encrypt_body(self.session_key, body)}
        send_json(self.sock, env)

    def send_private(self, to_user: str, text: str):
        ''' Send a private message to a specific user '''
        body = {"text": text}
        env = {"type":"priv","sender":self.username,"to":to_user,"ts":self.iso_now(),
               "payload": encrypt_body(self.session_key, body)}
        send_json(self.sock, env)

    def send_file_offer(self, to_user: str, path: str, size: int, file_id: str):
        ''' Send a file offer to a specific user (or broadcast with to_user="*")
            Includes a stable file_id so receivers can request the correct file.
            Includes file metadata: name, size, type (extension)
        '''
        import os.path
        filename = os.path.basename(path)   # Get the name of file ( ex: "document.pdf" )
        # Get file extension/type
        _, ext = os.path.splitext(filename)   # split into (root, ext)
        file_type = ext[1:] if ext else "unknown"  # get file type without dot
        
        meta = {
            "name": filename,
            "size": size,
            "type": file_type,
            "file_id": file_id
        }
        env = {"type":"file_offer","sender":self.username,"to":to_user,"ts":self.iso_now(),
               "payload": encrypt_body(self.session_key, meta)}
        send_json(self.sock, env)

    def send_file_chunk(self, to_user: str, file_id: str, seq: int, chunk, final: bool):
        '''
        This function sends a file chunk to a specific user. Accepts bytes or str for chunk.
        Input:
            - to_user: recipient username
            - file_id: unique identifier for the file transfer session
            - seq: sequence number of this chunk
            - chunk: bytes or str data of the chunk
            - final: boolean indicating if this is the final chunk
        Output: sends a "file_chunk" message to the server      
        '''
        if isinstance(chunk, bytes): # if chunk is bytes, decode it
            data_str = chunk.decode("latin1")
        else:

            data_str = chunk
        body = {"id": file_id, "seq": seq, "final": final, "data": data_str}
        env = {"type":"file_chunk","sender":self.username,"to":to_user,"ts":self.iso_now(),
               "payload": encrypt_body(self.session_key, body)}
        send_json(self.sock, env)

    def send_file_ack(self, to_user: str, file_id: str, accept: bool):
        ''' 
        This function send a file offer acknowledgment to a specific user 
        Input: 
            - to_user: recipient username
            - file_id: unique identifier for the file transfer session
            - accept: boolean indicating if the file offer is accepted
        '''
        body = {"id": file_id, "accept": accept}
        env = {"type":"file_ack","sender":self.username,"to":to_user,"ts":self.iso_now(),
               "payload": encrypt_body(self.session_key, body)}
        send_json(self.sock, env)

    def _recv_loop(self):
        ''' Thread function to receive messages from server '''
        try:
            while self.running:
                env = recv_json(self.sock)
                if self._on_message:  # if the UI handler attached, immediately pass the received message to that callback so that UI ready to display.
                    self._on_message(env)     
                else:
                    # No handler yet (UI not attached) → backlog to replay later
                    self._backlog.append(env)  # if the UI is not ready, store message in backlog
        except Exception:
            # Socket closed or error; notify UI
            self.running = False
            if self._on_message:
                self._on_message({"type":"system","sender":None,"to":"*","ts":self.iso_now(),
                                  "payload":{"text":"Disconnected."}})
