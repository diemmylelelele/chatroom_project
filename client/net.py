import socket, threading, datetime, json, os
from queue import Queue
from typing import Optional, Callable, Dict, Any

from common.protocol import send_json, recv_json
from common.crypto import aes_key, rsa_wrap_key, encrypt_body, decrypt_body

ENC = "utf-8"

class NetClient:
    def __init__(self, host: str, port: int, username: str, on_message: Callable[[Dict[str,Any]], None], avatar_id: int = 0):
        self.host, self.port, self.username = host, port, username
        self.avatar_id = avatar_id  # User's avatar ID (0-1)
        self.sock: Optional[socket.socket] = None
        self.on_message = on_message  # callback for incoming messages
        self.session_key: Optional[bytes] = None   # AES session key after key-exchange
        self.recv_thread: Optional[threading.Thread] = None   # thread for receiving messages
        self.running = False

    def iso_now(self):
        return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # Send auth with avatar_id
        send_json(self.sock, {"type":"auth","sender":None,"to":None,"ts":self.iso_now(),
                              "payload":{"username": self.username, "avatar_id": self.avatar_id}})
        # Receive RSA pub
        env = recv_json(self.sock)
        server_pub = env["payload"]["server_pub_pem"]
        # Generate AES session & wrap
        self.session_key = aes_key()
        # Encrypt the session AES key with server's RSA public key
        wrapped = rsa_wrap_key(server_pub, self.session_key)
        # Send wrapped key
        send_json(self.sock, {"type":"key","sender":self.username,"to":None,"ts":self.iso_now(),
                              "payload":{"wrapped": wrapped}})
        # Start listening for incoming messages from server
        self.running = True
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

    def close(self):
        try:
            if self.sock:
                send_json(self.sock, {"type":"system","sender":self.username,"to":None,"ts":self.iso_now(),
                                      "payload":{"event":"leave"}})
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
        '''
        meta = {"name": os.path.basename(path), "size": size, "file_id": file_id}
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
                self.on_message(env)
        except Exception:
            # Socket closed or error; notify UI
            self.running = False
            self.on_message({"type":"system","sender":None,"to":"*","ts":self.iso_now(),
                             "payload":{"text":"Disconnected."}})
