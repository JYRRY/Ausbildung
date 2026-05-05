"""Tests for jyry.services.crypto."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from jyry.config import Settings, get_settings
from jyry.services.crypto import CryptoError, decrypt_secret, encrypt_secret


def _alt_settings() -> Settings:
    """A Settings instance backed by a different Fernet key."""
    base = get_settings()
    other = base.model_copy(update={"fernet_key": _other_secret()})
    return other


def _other_secret():
    from pydantic import SecretStr

    return SecretStr(Fernet.generate_key().decode())


def test_round_trip_returns_original_plaintext():
    ct = encrypt_secret("super-secret-app-password")
    assert isinstance(ct, bytes)
    assert b"super-secret-app-password" not in ct
    assert decrypt_secret(ct) == "super-secret-app-password"


def test_each_encrypt_uses_fresh_iv():
    a = encrypt_secret("same plaintext")
    b = encrypt_secret("same plaintext")
    assert a != b  # Fernet embeds a fresh nonce/IV every call
    assert decrypt_secret(a) == decrypt_secret(b) == "same plaintext"


def test_decrypt_with_wrong_key_raises_crypto_error():
    ct = encrypt_secret("hello")
    with pytest.raises(CryptoError):
        decrypt_secret(ct, settings=_alt_settings())


def test_decrypt_garbage_raises_crypto_error():
    with pytest.raises(CryptoError):
        decrypt_secret(b"not a valid fernet token")


def test_empty_inputs_rejected():
    with pytest.raises(ValueError, match="refusing to encrypt"):
        encrypt_secret("")
    with pytest.raises(ValueError, match="refusing to decrypt"):
        decrypt_secret(b"")


def test_unicode_round_trip():
    plain = "كلمة سر معقدة 🤫 mit Umlauten: äöüß"
    assert decrypt_secret(encrypt_secret(plain)) == plain
