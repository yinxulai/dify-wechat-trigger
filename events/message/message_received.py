from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class MessageReceivedEvent(Event):
    def _on_event(self, request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        del request, parameters
        return Variables(variables=dict(payload))
