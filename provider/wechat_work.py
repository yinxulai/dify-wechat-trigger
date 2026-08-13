from __future__ import annotations

import json
from collections.abc import Mapping

from werkzeug import Request, Response

from dify_plugin.entities.trigger import EventDispatch, Subscription
from dify_plugin.errors.trigger import (
    TriggerDispatchError,
    TriggerValidationError,
)
from dify_plugin.interfaces.trigger import Trigger

from .wechat_work_callback import (
    CallbackAuthenticationError,
    CallbackPayloadError,
    WechatWorkCallback,
)
class WechatWorkTrigger(Trigger):
    def _dispatch_event(self, subscription: Subscription, request: Request) -> EventDispatch:
        token = subscription.properties.get("token")
        encoding_aes_key = subscription.properties.get("encoding_aes_key")
        if not isinstance(token, str) or not token or not isinstance(encoding_aes_key, str) or not encoding_aes_key:
            raise TriggerDispatchError("Callback Token and EncodingAESKey are required")

        callback = WechatWorkCallback(token, encoding_aes_key)
        try:
            decrypted = callback.decrypt_request(request)
        except CallbackAuthenticationError as exc:
            raise TriggerValidationError(str(exc)) from exc
        except CallbackPayloadError as exc:
            raise TriggerDispatchError(str(exc)) from exc

        if request.method == "GET":
            return EventDispatch(events=[], response=Response(decrypted, status=200))

        try:
            payload = json.loads(decrypted)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TriggerDispatchError("Decrypted callback payload must be valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise TriggerDispatchError("Decrypted payload must be a JSON object")
        if not payload.get("aibotid"):
            raise TriggerDispatchError("Missing aibotid")
        if not payload.get("msgid"):
            raise TriggerDispatchError("Missing msgid")

        return EventDispatch(
            events=["message_received"],
            response=Response('{"status":"ok"}', status=200, mimetype="application/json"),
            payload=dict(payload),
        )
