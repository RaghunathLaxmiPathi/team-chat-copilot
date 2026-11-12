"""T-43, T-60 to T-70: security headers, objectives (Success Rate and latency), and operations."""
from datetime import timedelta

import pytest

from app import clock
from app.slo import LAT_EDGES_MS, SloTracker
from tests.test_realtime import FakeSocket, frames_until


def ago(**kw):
    return clock.now() - timedelta(**kw)


def test_t43_security_headers_are_present(env):
    for path in ("/", "/healthz", "/api/v1/me"):
        h = env.client.get(path).headers
        assert "default-src 'self'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
        assert h["x-content-type-options"] == "nosniff" and h["referrer-policy"] == "no-referrer"


@pytest.mark.fast
def test_t60_latency_stays_under_the_targets(env, admin, alice, bob):
    group = env.group(alice, "Latency", bob)
    with bob.ws() as ws:
        ws.receive_json()
        for i in range(120):
            sent = env.send(alice, group, f"probe {i}").json()["message"]
            frame = frames_until(ws, "message")["message"]
            assert frame["id"] == sent["id"]
            ws.send_json({"type": "ack", "message_id": frame["id"]})
        ws.send_json({"type": "ping"})
        frames_until(ws, "pong")  # all acks are processed before the pong
    report = admin.get("/api/v1/slo?window=1h").json()["windows"]["1h"]["latency_ms"]
    print("\nlocal latency (service part only):", {k: v["value_ms"] for k, v in report.items() if k != "samples"})
    assert report["samples"] == 120
    for key, item in report.items():
        if key != "samples":
            assert item["status"] == "ok", (key, item)


def test_t61_success_rate_counts_only_service_failures(env, admin, alice, monkeypatch):
    before = env.svc.slo.window_report("1h")["success_rate"]["requests"]
    for _ in range(5):
        env.client.get("/api/v1/me")  # 401: a client error, not counted
    assert env.svc.slo.window_report("1h")["success_rate"]["requests"] == before
    alice.get("/api/v1/me")
    assert env.svc.slo.window_report("1h")["success_rate"]["requests"] == before + 1
    assert env.svc.slo.window_report("1h")["success_rate"]["failed"] == 0

    monkeypatch.setattr(env.svc.users, "list_all", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert alice.get("/api/v1/users").status_code == 500
    assert env.svc.slo.window_report("1h")["success_rate"]["failed"] == 1
    monkeypatch.undo()


def test_t62_percentiles_come_from_the_right_buckets():
    t = SloTracker()
    for ms in [90] * 50 + [180] * 25 + [350] * 15 + [650] * 5 + [900] * 4 + [1800]:
        t.record_latency_ms(ms)
    p = t.window_report("1h")["latency_ms"]
    assert [p[k]["value_ms"] for k in ("p50", "p75", "p90", "p95", "p99")] == [100, 200, 400, 700, 1000]
    assert all(p[k]["status"] == "ok" for k in ("p50", "p75", "p90", "p95", "p99"))
    t.record_latency_ms(float("inf"))  # an unconfirmed delivery lands in the slowest bucket
    assert t._window(60)[2][len(LAT_EDGES_MS)] == 1


def test_t63_windows_are_separate():
    t = SloTracker()
    for at in (ago(minutes=30), ago(hours=5), ago(days=10)):
        for _ in range(40):
            t.record_request(ok=True, at=at)
    counts = {w: t.window_report(w)["success_rate"]["requests"] for w in ("1h", "24h", "28d")}
    assert counts == {"1h": 40, "24h": 80, "28d": 120}


def test_t64_too_few_samples_reports_insufficient_data():
    t = SloTracker()
    for _ in range(29):
        t.record_request(ok=False)
    assert t.window_report("1h")["success_rate"]["status"] == "insufficient_data"
    t.record_request(ok=False)
    assert t.window_report("1h")["success_rate"]["status"] == "breach"
    for _ in range(99):
        t.record_latency_ms(50)
    lat = t.window_report("1h")["latency_ms"]
    assert lat["p95"]["status"] == "ok" and lat["p99"]["status"] == "insufficient_data"
    t.record_latency_ms(50)
    assert t.window_report("1h")["latency_ms"]["p99"]["status"] == "ok"
    assert t.report()["burn_rate_warning"] is False  # a quiet 24 hours is not "within target"


def test_t65_burn_rate_warning():
    t = SloTracker()
    for _ in range(100000):
        t.record_request(ok=True, at=ago(hours=5))
    for i in range(40):
        t.record_request(ok=(i != 0), at=ago(minutes=5))  # one failure in the last hour
    report = t.report()
    assert report["windows"]["1h"]["success_rate"]["status"] == "breach"
    assert report["windows"]["24h"]["success_rate"]["status"] == "ok"
    assert report["burn_rate_warning"] is True  # 1 hour is out of target, 24 hours still within
    healthy = SloTracker()
    for _ in range(100):
        healthy.record_request(ok=True)
    assert healthy.report()["burn_rate_warning"] is False


def test_t66_counts_survive_a_restart(env):
    t = env.svc.slo
    for _ in range(40):
        t.record_request(ok=True)
    for ms in range(40):
        t.record_latency_ms(ms)
    t.flush()
    fresh = SloTracker(env.svc.db)
    fresh.load()
    assert fresh.window_report("28d") == t.window_report("28d")


def test_t67_unconfirmed_deliveries_count_as_slow(env):
    hub = env.svc.hub
    conn = hub.register(FakeSocket(), "u1", clock.epoch() + 100)
    hub.publish_message({"id": "m1", "sender_id": "other"}, ["u1"], t0=clock.monotonic() - 11)
    hub.sweep()
    assert hub.deliveries_timed_out == 1
    assert env.svc.slo._window(60)[2][len(LAT_EDGES_MS)] == 1
    hub.unregister(conn)


def test_t68_operational_routes_are_protected_and_not_counted(env, admin, alice):
    assert env.client.get("/healthz").json() == {"status": "ok"}
    assert env.client.get("/readyz").json() == {"status": "ready"}
    before = env.svc.slo.window_report("1h")["success_rate"]["requests"]
    assert alice.get("/metrics").status_code == 403 and alice.get("/api/v1/slo").status_code == 403
    assert admin.get("/metrics").status_code == 200 and admin.get("/api/v1/slo").status_code == 200
    assert admin.get("/api/v1/slo?window=2h").status_code == 400
    env.client.get("/")
    assert env.svc.slo.window_report("1h")["success_rate"]["requests"] == before  # none of these are customer calls


@pytest.mark.fast
def test_t69_ten_times_the_expected_connections(env):
    hub, slo = env.svc.hub, env.svc.slo
    users = [f"u{i}" for i in range(100)]
    conns = [hub.register(FakeSocket(), u, clock.epoch() + 100) for u in users]
    for n in range(200):
        hub.publish_message({"id": f"m{n}", "sender_id": "sender", "seq": n}, users)
    for c in conns:
        assert c.close_code is None and c.queue.qsize() == 200
        seqs = [c.queue.get_nowait()["message"]["seq"] for _ in range(200)]
        assert seqs == list(range(200))  # in order on every connection
        for n in range(200):
            hub.handle_ack(c, f"m{n}")
    lat = slo.window_report("1h")["latency_ms"]
    assert lat["samples"] == 20000 and all(lat[k]["status"] == "ok" for k in ("p50", "p75", "p90", "p95", "p99"))
    for c in conns:
        hub.unregister(c)


def test_t70_error_shape_and_correlation_id(env, alice):
    cases = [env.client.get("/api/v1/me"), alice.get("/api/v1/conversations/nope"), alice.get("/api/v1/users/x/thread"),
             alice.post("/api/v1/users", {"username": "x", "display_name": "x"}),
             alice.post("/api/v1/conversations", {"type": "banana"})]
    for r in cases:
        body = r.json()["error"]
        assert set(body) == {"code", "message", "request_id"} and body["request_id"] == r.headers["x-request-id"]
    good = env.client.get("/api/v1/me", headers={"X-Request-ID": "trace-1234567890"})
    assert good.headers["x-request-id"] == "trace-1234567890"
    bad = env.client.get("/api/v1/me", headers={"X-Request-ID": "no spaces allowed!"})
    assert bad.headers["x-request-id"] != "no spaces allowed!"
