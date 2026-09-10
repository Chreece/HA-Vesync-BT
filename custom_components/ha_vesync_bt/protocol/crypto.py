"""VeSync VSV3 cryptographic helpers."""

from __future__ import annotations

import hashlib
import math
import secrets

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def aes_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """AES-CBC encrypt with PKCS7 padding."""
    if not plaintext:
        return b""
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def aes_decrypt(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    """AES-CBC decrypt with PKCS7 padding."""
    if not ciphertext:
        return b""
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def derive_k1(shared_secret: int, reversed_raw_mac: bytes) -> bytes:
    """Derive the VSV3 K1 session key."""
    material = (
        str(shared_secret).encode("ascii") + b"," + reversed_raw_mac
    )
    return hashlib.sha256(material).digest()[:16]


def is_prime(value: int) -> bool:
    """Return whether value is prime."""
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2

    divisor = 3
    limit = math.isqrt(value)
    while divisor <= limit:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def random_prime(low: int = 40000, high: int = 46340) -> int:
    """Return a random prime in the VSV3 LOW_SECURITY range."""
    rng = secrets.SystemRandom()
    while True:
        candidate = rng.randint(low, high)
        if is_prime(candidate):
            return candidate
