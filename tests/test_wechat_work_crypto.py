import base64

import pytest

from provider.wechat_work_crypto import WechatWorkCrypto, WechatWorkCryptoError


AES_KEY = base64.b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def test_crypto_round_trip_and_signature() -> None:
    crypto = WechatWorkCrypto("callback-token", AES_KEY, "")
    encrypted = crypto.encrypt(b'{"msgid":"message-1","msgtype":"text"}')
    signature = crypto.signature("1700000000", "nonce-1", encrypted)

    crypto.verify_signature(signature, "1700000000", "nonce-1", encrypted)
    assert crypto.decrypt(encrypted) == b'{"msgid":"message-1","msgtype":"text"}'


def test_signature_rejects_tampering() -> None:
    crypto = WechatWorkCrypto("callback-token", AES_KEY, "")
    encrypted = crypto.encrypt(b"message")

    with pytest.raises(WechatWorkCryptoError, match="signature"):
        crypto.verify_signature("invalid", "1700000000", "nonce-1", encrypted)


def test_receive_id_must_be_empty_for_wecom_ai_bot() -> None:
    sender = WechatWorkCrypto("callback-token", AES_KEY, "robot-app-id")
    receiver = WechatWorkCrypto("callback-token", AES_KEY, "")

    with pytest.raises(WechatWorkCryptoError, match="receive id"):
        receiver.decrypt(sender.encrypt(b"message"))
