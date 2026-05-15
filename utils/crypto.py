"""
utils/crypto.py — No-Brain-Trade Pro
AES-256-GCM encryption/decryption for storing user keypairs securely.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import ENCRYPTION_KEY


def _get_key() -> bytes:
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not set in environment")
    key = bytes.fromhex(ENCRYPTION_KEY)
    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY must be 32 bytes (64 hex chars)")
    return key


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns base64-encoded nonce+ciphertext."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(encoded: str) -> str:
    """Decrypt a base64-encoded nonce+ciphertext string."""
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encoded)
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()


def generate_encryption_key() -> str:
    """Generate a new 32-byte hex encryption key. Run once during setup."""
    return os.urandom(32).hex()


if __name__ == "__main__":
    print("Generated ENCRYPTION_KEY:", generate_encryption_key())
