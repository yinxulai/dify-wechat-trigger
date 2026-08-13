import base64

import pytest

from provider.wechat_work_crypto import (
    WechatWorkCrypto,
    WechatWorkCryptoError,
    find_robot,
    parse_robot_configs,
)


AES_KEY = base64.b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def test_crypto_round_trip_and_signature() -> None:
    crypto = WechatWorkCrypto("callback-token", AES_KEY, "robot-app-id")
    encrypted = crypto.encrypt(b'{"msgid":"message-1","msgtype":"text"}')
    signature = crypto.signature("1700000000", "nonce-1", encrypted)

    crypto.verify_signature(signature, "1700000000", "nonce-1", encrypted)
    assert crypto.decrypt(encrypted) == b'{"msgid":"message-1","msgtype":"text"}'


def test_signature_rejects_tampering() -> None:
    crypto = WechatWorkCrypto("callback-token", AES_KEY, "robot-app-id")
    encrypted = crypto.encrypt(b"message")

    with pytest.raises(WechatWorkCryptoError, match="signature"):
        crypto.verify_signature("invalid", "1700000000", "nonce-1", encrypted)


def test_receive_id_must_match_selected_robot() -> None:
    sender = WechatWorkCrypto("callback-token", AES_KEY, "robot-app-id")
    receiver = WechatWorkCrypto("callback-token", AES_KEY, "other-robot")

    with pytest.raises(WechatWorkCryptoError, match="selected robot"):
        receiver.decrypt(sender.encrypt(b"message"))


def test_parse_multiple_robot_configs() -> None:
    robots = parse_robot_configs(
        {
            "robot_id": ["support", "sales"],
            "robot_name": ["Support", "Sales"],
            "aibotid": ["bot-1", "bot-2"],
            "token": ["token-1", "token-2"],
            "encoding_aes_key": [AES_KEY, AES_KEY],
        }
    )

    assert [robot.id for robot in robots] == ["support", "sales"]
    assert find_robot(robots, "sales").aibotid == "bot-2"


def test_parse_selected_robot_subscription_properties() -> None:
    robots = parse_robot_configs(
        {
            "robot_id": "support",
            "robot_name": "Support",
            "aibotid": "bot-1",
            "token": "token-1",
            "encoding_aes_key": AES_KEY,
        }
    )

    assert len(robots) == 1
    assert robots[0].id == "support"


def test_parse_visual_robot_configs_rejects_mismatched_fields() -> None:
    with pytest.raises(ValueError, match="same non-zero length"):
        parse_robot_configs(
            {
                "robot_id": ["support", "sales"],
                "robot_name": ["Support"],
                "aibotid": ["bot-1", "bot-2"],
                "token": ["token-1", "token-2"],
                "encoding_aes_key": [AES_KEY, AES_KEY],
            }
        )


def test_parse_robot_configs_rejects_duplicate_ids() -> None:
    value = [
        {"id": "same", "name": "One", "aibotid": "bot-1", "token": "token", "encoding_aes_key": AES_KEY},
        {"id": "same", "name": "Two", "aibotid": "bot-2", "token": "token", "encoding_aes_key": AES_KEY},
    ]

    with pytest.raises(ValueError, match="duplicate robot id"):
        parse_robot_configs(value)
