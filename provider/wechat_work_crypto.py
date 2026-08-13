from __future__ import annotations

import base64
import hashlib
import os
import struct

from Crypto.Cipher import AES


class WechatWorkCryptoError(ValueError):
    pass


class WechatWorkCrypto:
    _BLOCK_SIZE = 32

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        if not token:
            raise ValueError("token must not be empty")
        self.token = token
        self.key = decode_aes_key(encoding_aes_key)
        self.receive_id = receive_id

    def verify_signature(self, signature: str, timestamp: str, nonce: str, encrypted: str) -> None:
        expected = self.signature(timestamp, nonce, encrypted)
        if not signature or not _constant_time_equal(signature, expected):
            raise WechatWorkCryptoError("invalid callback signature")

    def signature(self, timestamp: str, nonce: str, encrypted: str) -> str:
        parts = sorted((self.token, timestamp, nonce, encrypted))
        return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()

    def decrypt(self, encrypted: str) -> bytes:
        try:
            ciphertext = base64.b64decode(encrypted, validate=True)
            plaintext = AES.new(self.key, AES.MODE_CBC, self.key[:16]).decrypt(ciphertext)
            plaintext = _unpad(plaintext, self._BLOCK_SIZE)
        except (ValueError, TypeError) as exc:
            raise WechatWorkCryptoError("invalid encrypted callback payload") from exc

        if len(plaintext) < 20:
            raise WechatWorkCryptoError("decrypted callback payload is too short")
        message_length = struct.unpack(">I", plaintext[16:20])[0]
        message_end = 20 + message_length
        if message_end > len(plaintext):
            raise WechatWorkCryptoError("invalid callback message length")

        receive_id = plaintext[message_end:].decode("utf-8")
        if receive_id != self.receive_id:
            raise WechatWorkCryptoError("callback receive id does not match the configured value")
        return plaintext[20:message_end]

    def encrypt(self, message: bytes) -> str:
        plaintext = os.urandom(16) + struct.pack(">I", len(message)) + message + self.receive_id.encode("utf-8")
        ciphertext = AES.new(self.key, AES.MODE_CBC, self.key[:16]).encrypt(
            _pad(plaintext, self._BLOCK_SIZE)
        )
        return base64.b64encode(ciphertext).decode("ascii")


def decode_aes_key(encoding_aes_key: str) -> bytes:
    try:
        key = base64.b64decode(encoding_aes_key + "=", validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("encoding_aes_key must be a valid 43-character Base64 value") from exc
    if len(encoding_aes_key) != 43 or len(key) != 32:
        raise ValueError("encoding_aes_key must decode to exactly 32 bytes")
    return key


def _pad(value: bytes, block_size: int) -> bytes:
    padding_length = block_size - len(value) % block_size
    return value + bytes([padding_length]) * padding_length


def _unpad(value: bytes, block_size: int) -> bytes:
    if not value:
        raise ValueError("empty padded value")
    padding_length = value[-1]
    if padding_length < 1 or padding_length > block_size:
        raise ValueError("invalid PKCS#7 padding")
    if value[-padding_length:] != bytes([padding_length]) * padding_length:
        raise ValueError("invalid PKCS#7 padding")
    return value[:-padding_length]


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)
