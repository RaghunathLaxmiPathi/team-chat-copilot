"""Success Rate and delivery latency objectives (SLO-01 to SLO-05, DD-13 to DD-16).

Counts are kept in one-minute buckets, saved to the database, and summed per window.
"""
import json
import math
from bisect import bisect_left
from datetime import datetime, timedelta, timezone

from app import clock

LAT_EDGES_MS = [10, 25, 50, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000, 3000, 5000, 10000]
LATENCY_TARGETS_MS = {"p50": 200, "p75": 400, "p90": 700, "p95": 1000, "p99": 2000}
PERCENTILES = {"p50": 0.50, "p75": 0.75, "p90": 0.90, "p95": 0.95, "p99": 0.99}
SUCCESS_TARGET = 0.999
MIN_REQUESTS = 30
MIN_LATENCY_SAMPLES = 30
MIN_LATENCY_SAMPLES_P99 = 100
WINDOWS_MINUTES = {"1h": 60, "24h": 24 * 60, "28d": 28 * 24 * 60}


def _minute_key(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


class _Bucket:
    __slots__ = ("req_total", "req_failed", "lat_counts", "lat_total", "dirty")

    def __init__(self):
        self.req_total = 0
        self.req_failed = 0
        self.lat_counts = [0] * (len(LAT_EDGES_MS) + 1)
        self.lat_total = 0
        self.dirty = False


class SloTracker:
    def __init__(self, db=None):
        self.db = db
        self._buckets: dict[str, _Bucket] = {}

    # --- recording -------------------------------------------------------
    def _bucket(self, at: datetime | None) -> _Bucket:
        key = _minute_key(at or clock.now())
        b = self._buckets.get(key)
        if b is None:
            b = self._buckets[key] = _Bucket()
        b.dirty = True
        return b

    def record_request(self, ok: bool, at: datetime | None = None) -> None:
        b = self._bucket(at)
        b.req_total += 1
        if not ok:
            b.req_failed += 1

    def record_latency_ms(self, ms: float, at: datetime | None = None) -> None:
        b = self._bucket(at)
        b.lat_counts[bisect_left(LAT_EDGES_MS, ms)] += 1
        b.lat_total += 1

    # --- persistence -----------------------------------------------------
    def flush(self) -> None:
        if self.db is None:
            return
        dirty = [(k, b) for k, b in self._buckets.items() if b.dirty]
        if not dirty:
            return
        with self.db.transaction():
            for key, b in dirty:
                self.db.exec(
                    "INSERT OR REPLACE INTO slo_minutes (minute, req_total, req_failed, lat_counts, lat_total) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, b.req_total, b.req_failed, json.dumps(b.lat_counts), b.lat_total),
                )
        for _, b in dirty:
            b.dirty = False

    def load(self) -> None:
        if self.db is None:
            return
        cutoff = _minute_key(clock.now() - timedelta(minutes=WINDOWS_MINUTES["28d"]))
        for row in self.db.q_all("SELECT * FROM slo_minutes WHERE minute >= ?", (cutoff,)):
            b = _Bucket()
            b.req_total = row["req_total"]
            b.req_failed = row["req_failed"]
            counts = json.loads(row["lat_counts"])
            b.lat_counts = counts + [0] * (len(LAT_EDGES_MS) + 1 - len(counts))
            b.lat_total = row["lat_total"]
            self._buckets[row["minute"]] = b

    def _drop_old(self) -> None:
        cutoff = _minute_key(clock.now() - timedelta(minutes=WINDOWS_MINUTES["28d"]))
        for key in [k for k in self._buckets if k < cutoff]:
            del self._buckets[key]

    # --- reporting -------------------------------------------------------
    def _window(self, minutes: int) -> tuple[int, int, list[int], int]:
        cutoff = _minute_key(clock.now() - timedelta(minutes=minutes))
        total = failed = lat_total = 0
        counts = [0] * (len(LAT_EDGES_MS) + 1)
        for key, b in self._buckets.items():
            if key >= cutoff:
                total += b.req_total
                failed += b.req_failed
                lat_total += b.lat_total
                for i, c in enumerate(b.lat_counts):
                    counts[i] += c
        return total, failed, counts, lat_total

    @staticmethod
    def _percentile(counts: list[int], n: int, p: float) -> float | None:
        """Upper edge of the bucket where the running count reaches p. None means over the last edge."""
        threshold = math.ceil(p * n)
        running = 0
        for i, c in enumerate(counts):
            running += c
            if running >= threshold:
                return LAT_EDGES_MS[i] if i < len(LAT_EDGES_MS) else None
        return None

    def window_report(self, name: str) -> dict:
        total, failed, counts, lat_n = self._window(WINDOWS_MINUTES[name])
        if total < MIN_REQUESTS:
            success = {"requests": total, "failed": failed, "value": None,
                       "target": SUCCESS_TARGET, "status": "insufficient_data"}
        else:
            value = 1 - failed / total
            success = {"requests": total, "failed": failed, "value": round(value, 6),
                       "target": SUCCESS_TARGET, "status": "ok" if value >= SUCCESS_TARGET else "breach"}
        latency: dict = {"samples": lat_n}
        for key, p in PERCENTILES.items():
            minimum = MIN_LATENCY_SAMPLES_P99 if key == "p99" else MIN_LATENCY_SAMPLES
            target = LATENCY_TARGETS_MS[key]
            if lat_n < minimum:
                latency[key] = {"value_ms": None, "target_ms": target, "status": "insufficient_data"}
            else:
                value = self._percentile(counts, lat_n, p)
                ok = value is not None and value <= target
                latency[key] = {"value_ms": value, "target_ms": target, "status": "ok" if ok else "breach"}
        return {"success_rate": success, "latency_ms": latency}

    def report(self, window: str | None = None) -> dict:
        self._drop_old()
        names = [window] if window else list(WINDOWS_MINUTES)
        windows = {n: self.window_report(n) for n in names}
        warning = False
        if window is None:
            warning = (windows["1h"]["success_rate"]["status"] == "breach"
                       and windows["24h"]["success_rate"]["status"] == "ok")
        return {
            "targets": {"success_rate": SUCCESS_TARGET, "latency_ms": LATENCY_TARGETS_MS},
            "windows": windows,
            "burn_rate_warning": warning,
        }
