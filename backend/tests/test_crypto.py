import base64
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("MASTER_KEY", base64.b64encode(os.urandom(32)).decode())


def test_encrypt_decrypt_roundtrip():
    from app.core.crypto import decrypt, encrypt
    plaintext = b"my-ssh-private-key-content"
    ciphertext, nonce, auth_tag = encrypt(plaintext)
    assert ciphertext != plaintext
    assert len(nonce) == 12
    assert len(auth_tag) == 16
    result = decrypt(ciphertext, nonce, auth_tag)
    assert result == plaintext


def test_decrypt_with_tampered_ciphertext_fails():
    from app.core.crypto import encrypt, decrypt
    plaintext = b"secret-data"
    ciphertext, nonce, auth_tag = encrypt(plaintext)
    tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]
    with pytest.raises(Exception):
        decrypt(tampered, nonce, auth_tag)


def test_each_encryption_produces_unique_nonce():
    from app.core.crypto import encrypt
    _, nonce1, _ = encrypt(b"same data")
    _, nonce2, _ = encrypt(b"same data")
    assert nonce1 != nonce2
