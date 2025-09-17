from dataclasses import dataclass
from typing import Dict, Optional
import socket
from threading import Lock

@dataclass   # decorator to automatically generate init, repr, etc.
class Client:   # container class for storing info about each client
    username: str     # unique username
    sock: socket.socket  # socket connected to the client
    aes_key: Optional[bytes] = None    # Optional AES key for encrypting/decrypting messages

class ServerState:
    # This class manages all connected clients on the server
    def __init__(self):
        self.lock = Lock()  # creates a lock object to guard shared data
        self.clients: Dict[str, Client] = {}   # dictionary mapping usernames to Client objects

    def add_client(self, c: Client) -> bool:
        ''' This function adds a new client to the server state'''
        with self.lock:   # acquire the lock to ensure thread-safe access
            if c.username in self.clients:
                return False
            self.clients[c.username] = c
            return True

    def remove(self, username: str):
        ''' This function removes a client from the server state by username'''
        with self.lock:
            self.clients.pop(username, None)

    def get(self, username: str) -> Optional[Client]:
        ''' This function retrieves a client from the server state by username'''
        with self.lock:
            return self.clients.get(username)

    def users(self):
        ''' This function retrieves a list of all usernames in the server state'''
        with self.lock:
            return list(self.clients.keys())

    def broadcast(self, except_user: Optional[str] = None):
        ''' This function retrieves a list of all client sockets except for the specified username'''
        with self.lock:
            return [c.sock for u, c in self.clients.items() if u != except_user]

    def all_clients(self):
        ''' This function retrieves a list of all clients in the server state'''
        with self.lock:
            return list(self.clients.values())
