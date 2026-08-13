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
from .wechat_work_session import reply_sessions
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

        if payload.get("msgtype") == "stream":
            stream = payload.get("stream")
            stream_id = stream.get("id") if isinstance(stream, Mapping) else None
            if not isinstance(stream_id, str) or not stream_id:
                raise TriggerDispatchError("Missing stream id")
            session = reply_sessions.get_by_stream_id(stream_id)
            if session is None:
                raise TriggerDispatchError("Unknown stream id")
            response_payload = {
                "msgtype": "stream",
                "stream": {
                    "id": session.stream_id,
                    "finish": session.finished,
                    "content": session.content,
                },
            }
            return EventDispatch(
                events=[],
                response=Response(
                    callback.encrypt_response(response_payload, request.args["nonce"]),
                    status=200,
                    mimetype="application/json",
                ),
                payload={},
            )

        message_id = payload.get("msgid")
        if isinstance(message_id, str) and message_id:
            session = reply_sessions.get_or_create(message_id)
            response_payload = {
                "msgtype": "stream",
                "stream": {"id": session.stream_id, "finish": False, "content": ""},
            }
        else:
            response_payload = {}

        return EventDispatch(
            events=["message_received"],
            response=Response(
                callback.encrypt_response(response_payload, request.args["nonce"]),
                status=200,
                mimetype="application/json",
            ),
            payload=dict(payload),
        )
