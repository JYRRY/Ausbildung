"""Symmetric encryption for at-rest user secrets (Gmail App Password).

Wraps ``cryptography.fernet`` so model code never touches the raw key. The
key comes from ``Settings.fernet_key`` (a 32-byte URL-safe base64 string,
generated once at deploy time and kept out of git).
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from jyry.config import Settings, get_settings


class CryptoError(Exception):
    """Raised when a stored ciphertext can't be decrypted with the active key."""


@lru_cache(maxsize=1)
def _fernet(key: str) -> Fernet:
    return Fernet(key.encode("ascii") if isinstance(key, str) else key)


def _instance(settings: Settings | None = None) -> Fernet:
    s = settings or get_settings()
    return _fernet(s.fernet_key.get_secret_value())


def encrypt_secret(plaintext: str, *, settings: Settings | None = None) -> bytes:
    """Return the Fernet ciphertext (URL-safe base64 bytes) for ``plaintext``."""
    if not plaintext:
        raise ValueError("refusing to encrypt empty plaintext")
    return _instance(settings).encrypt(plaintext.encode("utf-8"))


def decrypt_secret(ciphertext: bytes, *, settings: Settings | None = None) -> str:
    """Return the plaintext for a Fernet ciphertext.

    Raises ``CryptoError`` if the ciphertext was forged, truncated, or
    encrypted with a different key (e.g. after a key rotation gone wrong).
    """
    if not ciphertext:
        raise ValueError("refusing to decrypt empty ciphertext")
    try:
        return _instance(settings).decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise CryptoError("ciphertext is invalid for the active FERNET_KEY") from exc
