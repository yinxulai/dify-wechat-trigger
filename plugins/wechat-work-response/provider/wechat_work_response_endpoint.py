from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from werkzeug import Request, Response

from dify_plugin.interfaces.endpoint import Endpoint


class WechatWorkResponseEndpoint(Endpoint):
    def _invoke(self, request: Request, values: Mapping, settings: Mapping) -> Response:
        del values
        try:
            payload = request.get_json(silent=False)
        except (TypeError, ValueError):
            return _json_response({"error": "request body must be valid JSON"}, 400)
        if not isinstance(payload, Mapping):
            return _json_response({"error": "request body must be a JSON object"}, 400)

        message_id = payload.get("message_id")
        content = payload.get("content")
        if not isinstance(message_id, str) or not message_id.strip():
            return _json_response({"error": "message_id is required"}, 400)
        if not isinstance(content, str) or not content:
            return _json_response({"error": "content is required"}, 400)

        backend_url = settings.get("response_backend_url")
        if not isinstance(backend_url, str) or not backend_url.startswith(("https://", "http://")):
            return _json_response({"error": "response_backend_url is not configured"}, 500)

        forwarded = dict(payload)
        forwarded["message_id"] = message_id.strip()
        try:
            backend_response = _post_json(backend_url, forwarded)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            return _json_response({"error": f"response backend request failed: {exc}"}, 502)
        return _json_response(
            {"status": "forwarded", "message_id": message_id.strip(), "backend": backend_response},
            200,
        )


class WechatWorkStatusEndpoint(WechatWorkResponseEndpoint):
    def _invoke(self, request: Request, values: Mapping, settings: Mapping) -> Response:
        response = request.get_json(silent=True)
        if not isinstance(response, Mapping):
            return super()._invoke(request, values, settings)
        status = response.get("status")
        if not isinstance(status, str) or not status.strip():
            return _json_response({"error": "status is required"}, 400)
        return super()._invoke(request, values, settings)


def _post_json(url: str, payload: Mapping) -> object:
    request = UrlRequest(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        raw_body = response.read()
    if not raw_body:
        return {}
    return json.loads(raw_body)


def _json_response(payload: Mapping, status: int) -> Response:
    return Response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status,
        content_type="application/json",
    )
