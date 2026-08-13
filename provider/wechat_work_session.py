from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass


@dataclass
class ReplySession:
    stream_id: str
    updated_at: float
    content: str = ""
    finished: bool = False


class ReplySessionStore:
    _ttl_seconds = 600

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions_by_message_id: dict[str, ReplySession] = {}
        self._sessions_by_stream_id: dict[str, ReplySession] = {}

    def get_or_create(self, message_id: str) -> ReplySession:
        now = time.time()
        with self._lock:
            self._cleanup(now)
            session = self._sessions_by_message_id.get(message_id)
            if session is None:
                session = ReplySession(stream_id=f"dify-{uuid.uuid4().hex}", updated_at=now)
                self._sessions_by_message_id[message_id] = session
                self._sessions_by_stream_id[session.stream_id] = session
            else:
                session.updated_at = now
            return session

    def get_by_stream_id(self, stream_id: str) -> ReplySession | None:
        with self._lock:
            self._cleanup(time.time())
            session = self._sessions_by_stream_id.get(stream_id)
            if session is not None:
                session.updated_at = time.time()
            return session

    def reply(self, message_id: str, content: str) -> ReplySession | None:
        with self._lock:
            self._cleanup(time.time())
            session = self._sessions_by_message_id.get(message_id)
            if session is None:
                return None
            session.content = content
            session.finished = True
            session.updated_at = time.time()
            return session

    def _cleanup(self, now: float) -> None:
        expired = [
            session
            for session in self._sessions_by_stream_id.values()
            if now - session.updated_at > self._ttl_seconds
        ]
        for session in expired:
            self._sessions_by_stream_id.pop(session.stream_id, None)
            for message_id, current in list(self._sessions_by_message_id.items()):
                if current is session:
                    self._sessions_by_message_id.pop(message_id, None)


reply_sessions = ReplySessionStore()
