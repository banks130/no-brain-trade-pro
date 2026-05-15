"""
utils/wallet.py — No-Brain-Trade Pro
Generate and manage user keypairs (non-custodial).
Users fund their own wallet; we only store the encrypted keypair.
"""

import base58
from solders.keypair import Keypair
from utils.crypto import encrypt, decrypt
from utils.logger import logger


def generate_keypair() -> dict:
    """
    Generate a new Solana keypair.
    Returns dict with public_key (str) and encrypted_secret (str).
    """
    kp = Keypair()
    secret_b58 = base58.b58encode(bytes(kp)).decode()
    return {
        "public_key": str(kp.pubkey()),
        "encrypted_secret": encrypt(secret_b58),
    }


def load_keypair(encrypted_secret: str) -> Keypair:
    """Decrypt and load a Keypair from encrypted storage."""
    secret_b58 = decrypt(encrypted_secret)
    secret_bytes = base58.b58decode(secret_b58)
    return Keypair.from_bytes(secret_bytes)


def pubkey_from_encrypted(encrypted_secret: str) -> str:
    """Get public key string without exposing private key."""
    kp = load_keypair(encrypted_secret)
    return str(kp.pubkey())
