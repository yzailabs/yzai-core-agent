import os
import base64
from cryptography.fernet import Fernet
from hashlib import sha256

SECRET = os.getenv("AGENT_WALLET_SECRET")

if not SECRET:
    raise Exception("AGENT_WALLET_SECRET not set")

# Convert hex secret → 32 byte key → Fernet format
key = sha256(bytes.fromhex(SECRET)).digest()
fernet_key = base64.urlsafe_b64encode(key)
cipher = Fernet(fernet_key)


def encrypt_private_key(private_key: str) -> str:
    return cipher.encrypt(private_key.encode()).decode()


def decrypt_private_key(encrypted_key: str) -> str:
    return cipher.decrypt(encrypted_key.encode()).decode()