from __future__ import annotations

import hashlib
import secrets


def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    Format: "{salt_hex}${key_hex}"
    """
    salt_hex = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_hex.encode("utf-8"),
        iterations=100_000,
    )
    return f"{salt_hex}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against `hash_password()` output."""
    try:
        salt_hex, key_hex = password_hash.split("$", 1)
    except ValueError:
        return False

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_hex.encode("utf-8"),
        iterations=100_000,
    )
    return secrets.compare_digest(key.hex(), key_hex)


