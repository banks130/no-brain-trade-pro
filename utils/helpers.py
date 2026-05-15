"""
utils/helpers.py — No-Brain-Trade Pro
"""

from datetime import datetime


def format_number(n: float, decimals: int = 2) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.{decimals}f}M"
    elif n >= 1_000:
        return f"{n/1_000:.{decimals}f}K"
    return f"{n:.{decimals}f}"


def shorten_address(addr: str, chars: int = 6) -> str:
    if len(addr) <= chars * 2:
        return addr
    return f"{addr[:chars]}...{addr[-chars:]}"


def now_ts() -> str:
    return datetime.utcnow().strftime("%H:%M:%S")


def lamports_to_sol(lamports: int) -> float:
    return lamports / 1_000_000_000
