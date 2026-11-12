"""Sliding-window send limit per user (FR-46, A-31). In-process, so one instance only (risk R-10)."""
import math
from collections import defaultdict, deque

from app import clock


class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = limit
        self.window = window_s
        self._events: dict[str, deque] = defaultdict(deque)

    def check_and_record(self, user_id: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds). Only allowed sends are recorded."""
        now = clock.monotonic()
        events = self._events[user_id]
        while events and now - events[0] >= self.window:
            events.popleft()
        if len(events) >= self.limit:
            return False, max(1, math.ceil(self.window - (now - events[0])))
        events.append(now)
        return True, 0
