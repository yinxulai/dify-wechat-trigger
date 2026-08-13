from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class MessageReceivedEvent(Event):
    def _on_event(self, request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        del request, parameters
        return Variables(variables=normalize_callback_payload(payload))


def normalize_callback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Expose useful message data without leaking the callback envelope."""
    output: dict[str, Any] = {}
    message_type = _string_value(payload.get("msgtype"))

    message: dict[str, Any] = {}
    _set_value(message, "id", payload.get("msgid"))
    _set_value(message, "type", message_type)
    message_body = payload.get(message_type) if message_type else None
    if isinstance(message_body, Mapping):
        content = message_body.get("content")
        if content is not None:
            _set_value(message, "content", content)
        details = _compact(message_body)
        if details:
            message["data"] = details
    _set_value(output, "message", message)

    sender = payload.get("from")
    if isinstance(sender, Mapping):
        sender_output: dict[str, Any] = {}
        _set_value(sender_output, "id", sender.get("userid"))
        _set_value(sender_output, "name", sender.get("alias") or sender.get("name"))
        _set_value(output, "sender", sender_output)

    conversation: dict[str, Any] = {}
    _set_value(conversation, "type", payload.get("chattype"))
    _set_value(conversation, "id", payload.get("chatid"))
    _set_value(conversation, "name", payload.get("chatname"))
    _set_value(output, "conversation", conversation)

    _set_value(output, "bot_id", payload.get("aibotid"))
    _set_value(output, "response_url", payload.get("response_url"))

    event = payload.get("event")
    if isinstance(event, Mapping):
        event_output: dict[str, Any] = {}
        _set_value(
            event_output,
            "type",
            event.get("eventtype") or event.get("event_type") or event.get("eventType"),
        )
        event_data = _compact(event)
        if event_data:
            event_output["data"] = event_data
        _set_value(output, "event", event_output)

    return output


def _set_value(target: dict[str, Any], key: str, value: Any) -> None:
    compacted = _compact(value)
    if compacted not in (None, "", {}, []):
        target[key] = compacted


def _compact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): compacted
            for key, item in value.items()
            if (compacted := _compact(item)) not in (None, "", {}, [])
        }
    if isinstance(value, list):
        return [compacted for item in value if (compacted := _compact(item)) not in (None, "", {}, [])]
    return value


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
