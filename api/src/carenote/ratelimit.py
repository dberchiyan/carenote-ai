"""A small in-process rate limit for the endpoints an anonymous caller can hammer.

Fixed window per client address. In-memory on purpose: one API process in this demo, and the
only guarded route is the demo login. A multi-process deployment would move the counter to
Redis or the database; the dependency's shape would not change.
"""

import threading
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request

from carenote.config import get_settings
from carenote.errors import ApiError, ErrorCode


class FixedWindow:
    def __init__(self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self.clock = clock
        self._hits: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            started, count = self._hits[key]
            if now - started >= self.window_s:
                started, count = now, 0
            count += 1
            self._hits[key] = (started, count)
            # Forget idle keys so the table does not grow for the life of the process.
            if len(self._hits) > 10_000:
                for k in [k for k, (s, _) in self._hits.items() if now - s >= self.window_s]:
                    del self._hits[k]
            return count <= self.limit

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request) -> str:
    # Behind the web proxy every request comes from the same host; the proxy forwards the
    # browser's address, which is what we want to count.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limit(window: FixedWindow) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if not window.allow(client_key(request)):
            raise ApiError(
                429,
                ErrorCode.RATE_LIMITED,
                "Too many attempts. Try again in a minute.",
                {"retry_after_s": int(window.window_s)},
            )

    return dependency


LOGIN_WINDOW = FixedWindow(limit=get_settings().login_rate_limit_per_minute, window_s=60)
