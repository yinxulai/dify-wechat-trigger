import base64
import json
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from dify_plugin.core.plugin_registration import PluginRegistration
from dify_plugin.entities.trigger import Subscription
from dify_plugin.errors.trigger import TriggerDispatchError, TriggerValidationError
from provider.wechat_work import WechatWorkTrigger
from provider.wechat_work_crypto import WechatWorkCrypto


AES_KEY = base64.b64encode(bytes(range(32))).decode("ascii").rstrip("=")
CALLBACK_PROPERTIES = {
    "token": "callback-token",
    "encoding_aes_key": AES_KEY,
}


def _subscription(properties=CALLBACK_PROPERTIES) -> Subscription:
    return Subscription(
        endpoint="https://example.test/callback",
        parameters={},
        properties=properties,
    )


def _trigger() -> WechatWorkTrigger:
    return WechatWorkTrigger(runtime=Mock())


def test_registers_provider_with_plugin_provider_name() -> None:
    registration = PluginRegistration(Path.cwd())

    assert [provider.identity.name for provider in registration.triggers_configuration] == [
        "wechat_work_trigger"
    ]


def _request(
    *,
    method: str = "POST",
    timestamp: str | None = None,
    payload: dict | None = None,
    decrypted: bytes | None = None,
) -> Request:
    timestamp = timestamp or str(int(time.time()))
    crypto = WechatWorkCrypto("callback-token", AES_KEY, "")
    message = decrypted or json.dumps(
        payload or {"aibotid": "bot-1", "msgid": "message-1", "msgtype": "text"}
    ).encode("utf-8")
    encrypted = crypto.encrypt(message)
    signature = crypto.signature(timestamp, "nonce-1", encrypted)
    query = {"timestamp": timestamp, "nonce": "nonce-1", "msg_signature": signature}
    body = None
    if method == "GET":
        query["echostr"] = encrypted
    else:
        body = json.dumps({"encrypt": encrypted})
    return Request(
        EnvironBuilder(
            method=method,
            path="/callback",
            query_string=query,
            data=body,
            content_type="application/json",
        ).get_environ()
    )


def test_dispatches_verified_post_callback() -> None:
    result = _trigger()._dispatch_event(_subscription(), _request())

    assert result.events == ["message_received"]
    assert result.payload["msgid"] == "message-1"
    assert result.response.status_code == 200
    encrypted_response = json.loads(result.response.get_data())
    response_crypto = WechatWorkCrypto("callback-token", AES_KEY, "")
    response_payload = response_crypto.decrypt(encrypted_response["encrypt"])
    assert json.loads(response_payload) == {}


def test_dispatches_event_without_message_fields() -> None:
    result = _trigger()._dispatch_event(
        _subscription(),
        _request(payload={"event": {"feedback_event": {"id": "feedback-1"}}}),
    )

    assert result.events == ["message_received"]
    assert result.payload["event"]["feedback_event"]["id"] == "feedback-1"


def test_returns_decrypted_echostr_for_wecom_url_probe() -> None:
    result = _trigger()._dispatch_event(_subscription(), _request(method="GET", decrypted=b"probe"))

    assert result.events == []
    assert result.response.status_code == 200
    assert result.response.get_data() == b"probe"


def test_rejects_expired_callback() -> None:
    expired = str(int(time.time()) - 301)

    with pytest.raises(TriggerValidationError, match="time window"):
        _trigger()._dispatch_event(_subscription(), _request(timestamp=expired))


def test_rejects_unsupported_callback_method() -> None:
    with pytest.raises(TriggerDispatchError, match="unsupported callback method"):
        _trigger()._dispatch_event(_subscription(), _request(method="PUT"))


def test_rejects_invalid_subscription_properties() -> None:
    with pytest.raises(TriggerDispatchError, match="Token and EncodingAESKey are required"):
        _trigger()._dispatch_event(_subscription(properties={}), _request())


def test_rejects_non_utf8_decrypted_payload() -> None:
    with pytest.raises(TriggerDispatchError, match="must be valid JSON"):
        _trigger()._dispatch_event(_subscription(), _request(decrypted=b"\xff"))
