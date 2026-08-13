from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from Crypto.Cipher import AES


class WechatWorkCryptoError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RobotConfig:
    id: str
    name: str
    aibotid: str
    token: str
    encoding_aes_key: str


def parse_robot_configs(value: Any) -> list[RobotConfig]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"robot configuration is not valid JSON: {exc.msg}") from exc

    if isinstance(value, Mapping):
        return _parse_visual_robot_configs(value)
    if not isinstance(value, list) or not value:
        raise ValueError("robot configuration must contain at least one robot")

    robots: list[RobotConfig] = []
    robot_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"robot configuration[{index}] must be an object")

        fields: dict[str, str] = {}
        for field in ("id", "name", "aibotid", "token", "encoding_aes_key"):
            field_value = item.get(field)
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(f"robot configuration[{index}].{field} must be a non-empty string")
            fields[field] = field_value.strip()

        if fields["id"] in robot_ids:
            raise ValueError(f"duplicate robot id: {fields['id']}")
        robot_ids.add(fields["id"])

        _decode_aes_key(fields["encoding_aes_key"])
        robots.append(RobotConfig(**fields))

    return robots


def _parse_visual_robot_configs(value: Mapping[str, Any]) -> list[RobotConfig]:
    fields = ("robot_id", "robot_name", "aibotid", "token", "encoding_aes_key")
    values: dict[str, list[Any]] = {}
    for field in fields:
        raw_value = value.get(field)
        if isinstance(raw_value, list):
            values[field] = raw_value
        elif raw_value is not None:
            values[field] = [raw_value]
        else:
            raise ValueError(f"missing robot configuration field: {field}")

    lengths = {len(items) for items in values.values()}
    if len(lengths) != 1 or not lengths or not next(iter(lengths)):
        raise ValueError("all robot configuration fields must have the same non-zero length")

    return parse_robot_configs(
        [
            {
                "id": values["robot_id"][index],
                "name": values["robot_name"][index],
                "aibotid": values["aibotid"][index],
                "token": values["token"][index],
                "encoding_aes_key": values["encoding_aes_key"][index],
            }
            for index in range(next(iter(lengths)))
        ]
    )


def find_robot(robots: list[RobotConfig], robot_id: str) -> RobotConfig:
    for robot in robots:
        if robot.id == robot_id:
            return robot
    raise ValueError(f"configured robot not found: {robot_id}")


class WechatWorkCrypto:
    _BLOCK_SIZE = 32

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        if not token:
            raise ValueError("token must not be empty")
        if not receive_id:
            raise ValueError("receive_id must not be empty")
        self.token = token
        self.key = _decode_aes_key(encoding_aes_key)
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
            raise WechatWorkCryptoError("callback receive id does not match the selected robot")
        return plaintext[20:message_end]

    def encrypt(self, message: bytes) -> str:
        plaintext = os.urandom(16) + struct.pack(">I", len(message)) + message + self.receive_id.encode("utf-8")
        ciphertext = AES.new(self.key, AES.MODE_CBC, self.key[:16]).encrypt(
            _pad(plaintext, self._BLOCK_SIZE)
        )
        return base64.b64encode(ciphertext).decode("ascii")


def _decode_aes_key(encoding_aes_key: str) -> bytes:
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
