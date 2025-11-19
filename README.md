# Real-Time Chatroom Application

## Project overview

The Real-Time Chatroom Application is a client–server system designed to facilitate real-time text communication between multiple users over a computer network. The primary goal of this project is to apply and demonstrate concepts learned in the Computer Networks course, including socket programming, concurrency, data transmission, and secure communication.

This project was developed to deepen understanding of:

- Socket-based communication and TCP reliability
- Multi-threaded server design for handling concurrent connections
- Secure data exchange using symmetric and asymmetric cryptography
- GUI-based client design for real-world user interaction

Through this project, key Computer Network principles are demonstrated — including the client–server model, network protocols, message framing, concurrency, and end-to-end encryption.


## Features

| #  | Function                | Description                                                     |
|----|-------------------------|-----------------------------------------------------------------|
| 1  | User Authentication     | Prompt for and enforce unique usernames.                        |
| 2  | Public Messaging        | Broadcast messages to all users.                                |
| 3  | Private Messaging       | Direct message between selected users.                          |
| 4  | Active User List        | Show all currently connected users.                             |
| 5  | GUI Interface           | Friendly, intuitive chat interface.                             |
| 6  | Concurrent Connections  | Server handles multiple users using threads.                    |
| 7  | File Sharing            | File send/receive with confirmation.                            |
| 8  | Emoji Support           | Add emojis through picker or commands.                          |
| 9  | Message Timestamps      | Show time of each message.                                      |
| 10 | Message Encryption      | Encrypt all messages before sending.       |
| 11 | Graceful Exit & Errors  | Handle disconnects, invalid input, and network failures.        |

## Report 
Detailed Report can be found [here](https://drive.google.com/file/d/18Zw24hqAr3qaV9iThbRUPo3ztG2Catx6/view?usp=sharing)

## Project structure

```
chatroom_project/
├─ README.md
├─ requirements.txt
├─ client/
│  ├─ __init__.py
│  ├─ login.py          # Login dialog (username + avatar)
│  ├─ main.py           # Client entry point (GUI launcher)
│  ├─ net.py            # Network client, encryption handshake, messaging
│  ├─ ui.py             # Chat UI 
│  └─ img/
│     └─ avatar/
|     └─ emoji_button.png
|     └─ file_button.png   
├─ common/
│  ├─ __init__.py
│  ├─ crypto.py         # RSA generation/wrap, AES encrypt/decrypt
│  ├─ messages.py       
│  └─ protocol.py       # JSON newline-delimited framing over TCP
└─ server/
	├─ __init__.py
	├─ main.py           # Server entry point (thread-per-connection)
	└─ state.py         
```

## How to run the project

1) Git clone the project
```
git clone https://github.com/diemmylelelele/chatroom_project.git
```

2) (Optional) Create and activate a virtual environment

```
python -m venv .venv
.\.venv\Scripts\Activate
```

3) Install dependencies

```
pip install -r requirements.txt
```

4) Start the server (listens on 0.0.0.0:5050)

```
python -m server.main
```

5) Start one or more clients (each in its own terminal). By default, the client connects to 127.0.0.1:5050 and opens a login window where you enter a unique username and choose an avatar:

```
python -m client.main
```

## Demo Usage 
This is a [demo video](https://drive.google.com/file/d/195jKZ3GQFrh3zIdOVDhe-WfTH65JvMxe/view?usp=sharing) showcasing how the project runs.


