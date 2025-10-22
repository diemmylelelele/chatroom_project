import socket, threading, traceback, datetime
from typing import Optional, Dict, Any
from common.protocol import send_json, recv_json
from common.crypto import rsa_generate, rsa_public_pem, rsa_unwrap_key, encrypt_body, decrypt_body
from server.state import ServerState, Client

HOST = "0.0.0.0"
PORT = 5050
ENC = "utf-8"

state = ServerState()
RSA_PRIV = rsa_generate()
RSA_PUB_PEM = rsa_public_pem(RSA_PRIV)

def iso_now():
    '''Return current UTC time in ISO format'''
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

def send_system(msg: str, to_sock: socket.socket = None):
    '''This function sends a system message to either a specific socket or broadcasts to all'''
    env = {"type":"system","sender":None,"to":"*","ts":iso_now(),"payload":{"text":msg}}
    if to_sock: # specific socket(send message to specific user)
        send_json(to_sock, env)
    else:  # broadcast to all
        for s in state.broadcast():
            send_json(s, env)

def push_userlist():
    '''This function pushes the updated user list to all clients'''
    users = state.users()
    print(f"[SERVER DEBUG] Pushing userlist: {users}")  # Debug
    env = {"type":"userlist","sender":None,"to":"*","ts":iso_now(),"payload":{"users": users}}
    for s in state.broadcast():
        send_json(s, env)

def handle_client(conn: socket.socket, addr):
    ''' This function handles communication with a connected client
        Inputs:
        - conn: socket object representing the client connection
        - addr: address of the connected client 
    '''
    username = None
    try:
        env = recv_json(conn)
        if env.get("type") != "auth":  # Check if the first message is auth
            send_json(conn, {"type":"error","sender":None,"to":None,"ts":iso_now(),"payload":{"code":"EXPECT_AUTH"}})
            conn.close(); return

        username = env["payload"]["username"]
        avatar_id = env["payload"].get("avatar_id", 0)  # Get avatar_id, default 0
        print(f"[SERVER DEBUG] User {username} connecting with avatar_id: {avatar_id}")  # Debug
        
        if not state.add_client(Client(username=username, sock=conn, avatar_id=avatar_id)):
            # If username is already taken → reject with "DUPLICATE_USERNAME" and close
            send_json(conn, {"type":"error","sender":None,"to":None,"ts":iso_now(),"payload":{"code":"DUPLICATE_USERNAME"}})
            conn.close(); return

        # Send RSA public key( belong to server) for key-exchange
        send_json(conn, {"type":"key","sender":None,"to":username,"ts":iso_now(),"payload":{"server_pub_pem": RSA_PUB_PEM}})

        # Receive client's wrapped AES key
        env = recv_json(conn)
        # Validate key message
        if env.get("type") != "key" or "wrapped" not in env.get("payload", {}):  # if not key message or missing "wrapped" field
            send_json(conn, {"type":"error","sender":None,"to":username,"ts":iso_now(),"payload":{"code":"EXPECT_AES_KEY"}})
            state.remove(username); conn.close(); return # remove client and close connection if invalid
        
        # Unwrap AES key and store in client state
        aes = rsa_unwrap_key(RSA_PRIV, env["payload"]["wrapped"])
        c = state.get(username)
        if c is not None:
            c.aes_key = aes

        send_system(f"{username} joined the chatroom.")
        push_userlist()

        # Main loop: route without decrypting (envelope-only)
        while True:
            env = recv_json(conn)
            etype = env.get("type")
            if etype in ("pub","priv","file_offer","file_chunk","file_ack"):
                route(env)
            elif etype == "system" and env["payload"].get("event") == "leave":
                break
            else:
                # ignore/notify
                send_json(conn, {"type":"error","sender":None,"to":username,"ts":iso_now(),"payload":{"code":"UNKNOWN_TYPE"}})

    except Exception:
        # print for server operator
        traceback.print_exc()
    finally:
        if username:
            state.remove(username)
            send_system(f"{username} left the chatroom.")
            push_userlist()
        try:
            conn.close()
        except Exception:
            pass

def route(env: Dict[str, Any]):
    to = env.get("to")
    sender = env.get("sender")
    cs = state.get(sender)
    if not cs or not cs.aes_key:
        return

    # Decrypt body with sender's AES session key
    try:
        body = decrypt_body(cs.aes_key, env["payload"])
    except Exception:
        # If decryption fails, drop silently
        return

    if env["type"] == "pub":  # if public message, broadcast to all (sender will see echo)
        # Re-encrypt for each recipient using their own AES key
        for rcpt in state.all_clients():
            try:
                env2 = dict(env)
                env2["to"] = "*"
                env2["payload"] = encrypt_body(rcpt.aes_key, body)
                send_json(rcpt.sock, env2)
            except Exception:
                continue
    elif env["type"] == "file_offer" and to == "*":
        # broadcast file offer to everyone except the sender
        for rcpt in state.all_clients():
            if rcpt.username == sender or not rcpt.aes_key:
                continue
            try:
                env2 = dict(env)
                env2["to"] = rcpt.username
                env2["payload"] = encrypt_body(rcpt.aes_key, body)
                send_json(rcpt.sock, env2)
            except Exception:
                continue
    elif env["type"] in ("priv","file_offer","file_chunk","file_ack"):
        # if private message or file transfer, send only to the specified recipient
        c = state.get(to)
        if c and c.aes_key:
            try:
                env2 = dict(env)
                env2["payload"] = encrypt_body(c.aes_key, body)
                send_json(c.sock, env2)
            except Exception:
                pass
        else:
            # bounce error to sender
            if cs:
                err = {"type":"error","sender":None,"to":sender,"ts":iso_now(),
                       "payload":{"code":"USER_NOT_FOUND","user":to}}
                send_json(cs.sock, err)

def main():
    print(f"Server listening on {HOST}:{PORT}")
    with socket.create_server((HOST, PORT)) as srv:
        while True:
            conn, addr = srv.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
