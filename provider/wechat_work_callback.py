from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import Any

from werkzeug import Request

from .wechat_work_crypto import WechatWorkCrypto, WechatWorkCryptoError


class CallbackAuthenticationError(ValueError):
    pass


class CallbackPayloadError(ValueError):
    pass


class WechatWorkCallback:
    _ALLOWED_METHODS = {"GET", "POST"}
    _MAX_CLOCK_SKEW_SECONDS = 300
    _MAX_BODY_BYTES = 1024 * 1024
    _MAX_ENCRYPTED_BYTES = 2 * 1024 * 1024

    def __init__(self, token: str, encoding_aes_key: str, clock: Callable[[], float] = time.time) -> None:
        self._crypto = WechatWorkCrypto(token, encoding_aes_key, "")
        self._clock = clock

    def decrypt_request(self, request: Request) -> bytes:
        if request.method not in self._ALLOWED_METHODS:
            raise CallbackPayloadError(f"unsupported callback method: {request.method}")

        timestamp = self._required_query_parameter(request, "timestamp")
        nonce = self._required_query_parameter(request, "nonce")
        signature = self._required_query_parameter(request, "msg_signature")
        self._validate_timestamp(timestamp)

        if request.method == "GET":
            encrypted = self._required_query_parameter(request, "echostr")
        else:
            encrypted = self._parse_encrypted_envelope(request)

        if len(encrypted.encode("utf-8")) > self._MAX_ENCRYPTED_BYTES:
            raise CallbackPayloadError("encrypted callback payload is too large")

        try:
            self._crypto.verify_signature(signature, timestamp, nonce, encrypted)
            return self._crypto.decrypt(encrypted)
        except WechatWorkCryptoError as exc:
            raise CallbackAuthenticationError("callback authentication failed") from exc

    def _validate_timestamp(self, timestamp: str) -> None:
        try:
            timestamp_value = int(timestamp)
        except ValueError as exc:
            raise CallbackAuthenticationError("invalid callback timestamp") from exc
        if abs(self._clock() - timestamp_value) > self._MAX_CLOCK_SKEW_SECONDS:
            raise CallbackAuthenticationError("callback timestamp is outside the allowed time window")

    @staticmethod
    def _required_query_parameter(request: Request, name: str) -> str:
        value = request.args.get(name, "")
        if not value:
            raise CallbackAuthenticationError(f"missing callback query parameter: {name}")
        return value

    def _parse_encrypted_envelope(self, request: Request) -> str:
        content_length = request.content_length
        if content_length is not None and content_length > self._MAX_BODY_BYTES:
            raise CallbackPayloadError("callback request body is too large")

        raw_body = request.get_data(cache=False)
        if len(raw_body) > self._MAX_BODY_BYTES:
            raise CallbackPayloadError("callback request body is too large")
        try:
            envelope: Any = json.loads(raw_body or b"{}")
        except json.JSONDecodeError as exc:
            raise CallbackPayloadError("callback request body must be valid JSON") from exc
        if not isinstance(envelope, Mapping):
            raise CallbackPayloadError("callback request body must be a JSON object")

        encrypted = envelope.get("encrypt")
        if not isinstance(encrypted, str) or not encrypted:
            raise CallbackPayloadError("missing encrypt field")
        return encrypted
