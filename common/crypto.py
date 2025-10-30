import base64, json, os
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def rsa_generate(bits: int = 2048):
    ''' 
    The function generates an RSA private key. 
        Input: key size in bits (default 2048)
        Output: private key object
    '''
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)

def rsa_public_pem(priv) -> str:
    ''' 
    The function returns the  public key from a private key. 
        Input: 
            - RSA private key object
        Output: 
            - PEM string of the public key
    '''
    pub = priv.public_key()
    # Encode public key in PEM format (Base64 + header/footer)
    pem = pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode()  # decode bytes to str

def rsa_wrap_key(pub_pem: str, key_bytes: bytes) -> str:
    ''' 
    This function encrypt a AES key using the recipient's RSA public key. 
    Input: 
        - pub_pem: recipient’s RSA public key in PEM format (string) 
        - key_bytes: the AES key (binary)
    Output: Base64 string of the wrapped key
    '''
    # Load the public key from PEM
    pub = serialization.load_pem_public_key(pub_pem.encode())
    # Encrypt the AES key using RSA 
    wrapped = pub.encrypt(
        key_bytes,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(),
                     label=None)
    )
    return b64(wrapped)  # binary ciphertext for AES key

def rsa_unwrap_key(priv, wrapped_b64: str) -> bytes:
    '''
    This function decrypts AES key using the recipient's RSA private key. 
    Input:
        - priv: recipient’s RSA private key object
        - wrapped_b64: Base64 string of the wrapped AES key
    Output: the unwrapped AES key in bytes
    '''
    wrapped = b64d(wrapped_b64)
    return priv.decrypt(
        wrapped,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(),
                     label=None)
    )

def aes_key() -> bytes:
    '''This function generates a random 256-bit AES key'''
    return AESGCM.generate_key(bit_length=256)

def aes_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> Tuple[str,str,str]:
    '''
    This function encrypts plaintext using AES-GCM. 
    Input:
        - key: AES key in bytes (256 bits)
        - plaintext: data to encrypt in bytes
        - aad: additional authenticated data (optional, bytes)
    Output: tuple of Base64 strings (nonce, ciphertext, tag)
    '''
    # Create AESGCM object using provided key
    aes = AESGCM(key)
    nonce = os.urandom(12)  # random 96-bit nonce
    ct = aes.encrypt(nonce, plaintext, aad)  # returns ct||tag
    # cryptography puts tag at the end; but for transport we keep as one blob
    return b64(nonce), b64(ct[:-16]), b64(ct[-16:])

def aes_decrypt(key: bytes, nonce_b64: str, ct_b64: str, tag_b64: str, aad: bytes = b"") -> bytes:
    '''
    This function decrypts ciphertext using AES-GCM.
    Input:
        - key: AES key in bytes (256 bits)
        - nonce_b64: Base64 string of the nonce
        - ct_b64: Base64 string of the ciphertext
        - tag_b64: Base64 string of the authentication tag
        - aad: additional authenticated data (optional, bytes)
    Output: decrypted plaintext in bytes
    '''
    aes = AESGCM(key)
    nonce = b64d(nonce_b64)
    ct = b64d(ct_b64) + b64d(tag_b64)
    return aes.decrypt(nonce, ct, aad)

def pack_encrypted(nonce_b64: str, ct_b64: str, tag_b64: str) -> dict:
    '''
    This function packs the encrypted components into a dictionary.
        Input: Base64 strings of nonce, ciphertext, tag
        Output: dictionary with structure {"enc": {"n": nonce, "c": ciphertext, "t": tag}}
    '''
    return {"enc": {"n": nonce_b64, "c": ct_b64, "t": tag_b64}}

def unpack_encrypted(d: dict) -> Tuple[str,str,str]:
    '''
    This function unpacks the encrypted components from a dictionary.
        Input: dictionary with structure {"enc": {"n": nonce, "c": ciphertext, "t": tag}}
        Output: tuple of Base64 strings (nonce, ciphertext, tag)
    '''
    e = d["enc"]
    return e["n"], e["c"], e["t"]

def b64(b: bytes) -> str:
    ''' This function encodes bytes to a Base64 string '''
    return base64.b64encode(b).decode()

def b64d(s: str) -> bytes:
    ''' This function decodes a Base64 string to bytes '''
    return base64.b64decode(s.encode())


def encrypt_body(key: bytes, body: dict) -> dict:
    ''' 
    This function encrypts a message body (dictionary) using AES-GCM and packs it.
    Input:
        - key: AES key in bytes (256 bits)
        - body: message body as a dictionary
    Output: dictionary with structure {"enc": {"n": nonce, "c": ciphertext, "t": tag}}
    '''
    nonce, ct, tag = aes_encrypt(key, json.dumps(body, ensure_ascii=False).encode())
    return pack_encrypted(nonce, ct, tag)

def decrypt_body(key: bytes, payload: dict) -> dict:
    ''' 
    This function unpacks and decrypts an encrypted message body using AES-GCM.
    Input:
        - key: AES key in bytes (256 bits)
        - payload: dictionary with structure {"enc": {"n": nonce, "c": ciphertext, "t": tag}}
    Output: decrypted message body as a dictionary
    '''
    n,c,t = unpack_encrypted(payload)
    data = aes_decrypt(key, n, c, t)
    return json.loads(data.decode())

