from dataclasses import dataclass
from typing import Optional, Dict, Any

# Envelope fields remain in plaintext so server can route without decrypting.
@dataclass
class Envelope:
    type: str            # "auth" | "pub" | "priv" | "system" | "userlist" | "file_offer" | "file_chunk" | "file_ack" | "key" | "error"
    sender: Optional[str]
    to: Optional[str]    # username or "*"
    ts: str              # ISO 8601
    payload: Dict[str, Any]  # may be plaintext (handshake) or encrypted body (after session established)

