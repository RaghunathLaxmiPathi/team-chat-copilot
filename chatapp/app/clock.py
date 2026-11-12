"""Single place that reads the time, so tests can control it."""
import time
from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    """UTC time in ISO 8601 form with milliseconds, always ending in Z."""
    dt = dt or now()
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def epoch() -> float:
    return time.time()


def monotonic() -> float:
    # perf_counter has sub-millisecond resolution on every platform (time.monotonic ticks every ~15 ms on Windows).
    return time.perf_counter()
