from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen


def invoke_response(payload: Mapping, require_status: bool) -> Mapping:
    message_id = payload.get("message_id")
    content = payload.get("content")
    if not isinstance(message_id, str) or not message_id.strip():
        return {"error": "message_id is required"}
    if not isinstance(content, str) or not content:
        return {"error": "content is required"}
    if require_status:
        status = payload.get("status")
        if not isinstance(status, str) or not status.strip():
            return {"error": "status is required"}

    response_url = payload.get("response_url")
    if not is_wecom_response_url(response_url):
        return {"error": "response_url must be an HTTPS WeCom API URL"}

    forwarded = dict(payload)
    forwarded["message_id"] = message_id.strip()
    try:
        backend_response = post_json(response_url, forwarded)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return {"error": f"response backend request failed: {exc}"}
    return {"status": "forwarded", "message_id": message_id.strip(), "backend": backend_response}


def post_json(url: str, payload: Mapping) -> object:
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


def is_wecom_response_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == "qyapi.weixin.qq.com"
