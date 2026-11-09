"""Short in-memory conversation history per call or chat session. Replace with Redis before real use."""
import threading

MAX_MESSAGES = 20


class SessionStore:
    def __init__(self) -> None:
        self._histories: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def history(self, session_id: str) -> list[dict]:
        with self._lock:
            history = self._histories.setdefault(session_id, [])
            if len(history) > MAX_MESSAGES:
                del history[: len(history) - MAX_MESSAGES]
            return history
