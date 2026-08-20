import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

_key: bytes = settings.master_key_bytes
_aesgcm = AESGCM(_key)


def encrypt(plaintext: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt with AES-256-GCM. Returns (ciphertext, nonce, auth_tag)."""
    nonce = os.urandom(12)
    ct_with_tag = _aesgcm.encrypt(nonce, plaintext, None)
    ciphertext = ct_with_tag[:-16]
    auth_tag = ct_with_tag[-16:]
    return ciphertext, nonce, auth_tag


def decrypt(ciphertext: bytes, nonce: bytes, auth_tag: bytes) -> bytes:
    """Decrypt with AES-256-GCM. Raises on tag mismatch."""
    ct_with_tag = ciphertext + auth_tag
    return _aesgcm.decrypt(nonce, ct_with_tag, None)
