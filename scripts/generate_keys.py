#!/usr/bin/env python3
"""
generate_keys.py — Generate encryption keys for No-Brain-Trade Pro
Run this once before deployment
"""

import secrets
import base64
import os

def generate_keys():
    """Generate secure random keys"""
    # Generate encryption key (32 bytes for AES-256)
    encryption_key = secrets.token_bytes(32)
    encryption_key_b64 = base64.b64encode(encryption_key).decode()
    
    # Generate secret key for sessions
    secret_key = secrets.token_urlsafe(32)
    
    print("\n" + "="*50)
    print("NO-BRAIN-TRADE PRO - GENERATED KEYS")
    print("="*50)
    print("\n📋 COPY THESE TO YOUR .env FILE:\n")
    print(f"ENCRYPTION_KEY={encryption_key_b64}")
    print(f"SECRET_KEY={secret_key}")
    print("\n" + "="*50)
    print("⚠️  IMPORTANT:")
    print("- Save these keys securely")
    print("- Never share or commit them to git")
    print("- If you lose ENCRYPTION_KEY, user wallets cannot be decrypted!")
    print("="*50 + "\n")
    
    # Save to file (excluded from git)
    with open(".env.keys", "w") as f:
        f.write(f"ENCRYPTION_KEY={encryption_key_b64}\n")
        f.write(f"SECRET_KEY={secret_key}\n")
    
    print("✅ Keys also saved to .env.keys (keep this file safe!)")

if __name__ == "__main__":
    generate_keys()
