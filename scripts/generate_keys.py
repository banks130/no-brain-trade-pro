"""
scripts/generate_keys.py — No-Brain-Trade Pro
Run once to generate your ENCRYPTION_KEY and SECRET_KEY for .env
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 50)
print("  NO-BRAIN-TRADE PRO — Key Generator")
print("=" * 50)
print()
print("Add these to your Railway environment variables:")
print()
print(f"ENCRYPTION_KEY={os.urandom(32).hex()}")
print(f"SECRET_KEY={os.urandom(32).hex()}")
print()
print("⚠️  ENCRYPTION_KEY encrypts user keypairs.")
print("    NEVER change it after users have wallets.")
print("    Back it up somewhere safe.")
