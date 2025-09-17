# FUV Chatroom Project


## Install dependencies


Install dependencies once in the project root:

```
pip install -r requirements.txt
```

## How to run

Always run modules from the project root using `-m` so package imports work.

1) Start the server :

```
python -m server.main
```

2) Start one or more clients (each in its own PowerShell window/terminal):

```
python -m client.main --user user1
python -m client.main --user user2
```
Example connecting to a remote server:

```
python -m client.main --host 192.168.1.50 --port 5050 --user alice
```

