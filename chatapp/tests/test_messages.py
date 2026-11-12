"""T-12, T-20 to T-29, T-77, T-78: messages."""
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


@pytest.mark.fast
def test_t12_concurrent_sends_get_unique_gap_free_numbers(env, admin):
    senders = [env.new_user(admin, f"sender{i}") for i in range(10)]
    group = env.group(senders[0], "Busy", *senders[1:])

    def work(s):
        return [env.send(s, group, f"msg from {s.user['username']} #{n}").status_code for n in range(10)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, senders))
    assert all(code == 201 for codes in results for code in codes)
    msgs = senders[0].get(f"/api/v1/conversations/{group}/messages?limit=50").json()["messages"]
    page2 = senders[0].get(f"/api/v1/conversations/{group}/messages?limit=50&before_seq={msgs[0]['seq']}").json()["messages"]
    seqs = [m["seq"] for m in page2 + msgs]
    assert seqs == list(range(1, 101))


def test_t20_send_and_validate(env, alice, bob):
    dm = env.dm(alice, bob)
    ok = env.send(alice, dm, "  Hello **world**  ")
    assert ok.status_code == 201
    assert ok.json()["message"]["body"] == "Hello **world**"
    for bad in ("", "   ", "x" * 4001):
        assert env.send(alice, dm, bad).status_code == 400, len(bad)
    assert env.send(alice, dm, "x" * 4000).status_code == 201
    short_id = alice.post(f"/api/v1/conversations/{dm}/messages", {"client_msg_id": "short", "body": "hi"})
    assert short_id.status_code == 400


def test_t21_retry_is_idempotent(env, alice, bob):
    dm = env.dm(alice, bob)
    other = env.group(alice, "Other", bob)
    payload = {"client_msg_id": "retry-12345678", "body": "only once"}
    first = alice.post(f"/api/v1/conversations/{dm}/messages", payload)
    second = alice.post(f"/api/v1/conversations/{dm}/messages", payload)
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["duplicate"] is True
    assert first.json()["message"]["id"] == second.json()["message"]["id"]
    assert env.svc.db.scalar("SELECT COUNT(*) FROM messages WHERE client_msg_id = ?", ("retry-12345678",)) == 1
    clash = alice.post(f"/api/v1/conversations/{other}/messages", payload)
    assert clash.status_code == 409


def test_t22_acknowledged_message_survives_a_restart(env, alice, bob):
    dm = env.dm(alice, bob)
    sent = env.send(alice, dm, "write me down").json()["message"]
    app2 = create_app(env.settings, start_background=False)  # a new service on the same files
    with TestClient(app2) as client2:
        r = client2.get(f"/api/v1/conversations/{dm}/messages", headers=alice.headers)
        assert r.status_code == 200
        assert [(m["id"], m["seq"], m["body"]) for m in r.json()["messages"]] == [(sent["id"], 1, "write me down")]
    app2.state.svc.db.close()


def test_t23_threads(env, alice, bob):
    dm = env.dm(alice, bob)
    other = env.dm(alice, env.login("carol"))
    root = env.send(alice, dm, "question?").json()["message"]
    reply = env.send(bob, dm, "answer", reply_to_id=root["id"]).json()["message"]
    nested = env.send(alice, dm, "thanks", reply_to_id=reply["id"]).json()["message"]
    assert reply["reply_to_id"] == root["id"] and nested["reply_to_id"] == root["id"]
    assert env.send(alice, other, "wrong place", reply_to_id=root["id"]).status_code == 400
    thread = alice.get(f"/api/v1/messages/{nested['id']}/thread").json()
    assert thread["root"]["id"] == root["id"]
    assert [r["body"] for r in thread["replies"]] == ["answer", "thanks"]


def test_t25_rate_limit(env, alice, bob, carol):
    dm = env.dm(alice, bob)
    for i in range(30):
        assert env.send(alice, dm, f"m{i}").status_code == 201
    blocked = env.send(alice, dm, "one too many")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert env.send(bob, dm, "still fine").status_code == 201


def test_t26_delete_own_message_reaches_every_copy(env, alice, bob):
    dm = env.dm(alice, bob)
    up = alice.upload(dm, "plan.pdf", b"%PDF-1.4 secret", "application/pdf")
    assert up.status_code == 201
    sent = env.send(alice, dm, "zebrawordtext for @bob", attachment_ids=[up.json()["id"]]).json()["message"]
    reply = env.send(bob, dm, "I saw it", reply_to_id=sent["id"]).json()["message"]
    assert len(list(Path(env.settings.attachment_dir).iterdir())) == 1
    assert env.svc.db.scalar("SELECT COUNT(*) FROM notifications WHERE message_id = ?", (sent["id"],)) == 1

    assert alice.delete(f"/api/v1/messages/{sent['id']}").status_code == 204
    msgs = bob.get(f"/api/v1/conversations/{dm}/messages").json()["messages"]
    assert msgs[0]["deleted"] is True and msgs[0]["body"] is None and msgs[0]["attachments"] == []
    assert msgs[1]["id"] == reply["id"]  # replies stay
    assert bob.get("/api/v1/search?q=zebrawordtext").json()["results"] == []
    assert list(Path(env.settings.attachment_dir).iterdir()) == []
    assert env.svc.db.scalar("SELECT COUNT(*) FROM mentions") == 0
    assert env.svc.db.scalar("SELECT COUNT(*) FROM notifications WHERE message_id = ?", (sent["id"],)) == 0
    assert env.svc.db.scalar("SELECT body FROM messages WHERE id = ?", (sent["id"],)) is None
    thread = bob.get(f"/api/v1/messages/{reply['id']}/thread").json()
    assert thread["root"]["deleted"] is True and len(thread["replies"]) == 1
    assert env.send(bob, dm, "reply to gone", reply_to_id=sent["id"]).status_code == 400


def test_t27_only_the_author_can_delete(env, admin, alice, bob):
    group = env.group(alice, "G", bob, admin)
    msg = env.send(alice, group, "mine").json()["message"]
    assert bob.delete(f"/api/v1/messages/{msg['id']}").status_code == 403
    assert admin.delete(f"/api/v1/messages/{msg['id']}").status_code == 403
    assert alice.delete(f"/api/v1/messages/{msg['id']}").status_code == 204
    assert alice.delete(f"/api/v1/messages/{msg['id']}").status_code == 204  # idempotent


@pytest.mark.fast
def test_t28_paging_before_after_around(env, alice, bob):
    dm = env.dm(alice, bob)
    for i in range(1, 121):
        assert env.send(alice, dm, f"n{i}").status_code == 201
    base = f"/api/v1/conversations/{dm}/messages"

    newest = alice.get(base).json()
    assert [m["seq"] for m in newest["messages"]] == list(range(71, 121))
    assert newest["has_more_before"] is True and newest["has_more_after"] is False

    earlier = alice.get(f"{base}?before_seq=71").json()
    assert [m["seq"] for m in earlier["messages"]] == list(range(21, 71))
    assert earlier["has_more_before"] is True and earlier["has_more_after"] is True

    later = alice.get(f"{base}?after_seq=100").json()
    assert [m["seq"] for m in later["messages"]] == list(range(101, 121))
    assert later["has_more_after"] is False

    around = alice.get(f"{base}?around_seq=60").json()
    assert [m["seq"] for m in around["messages"]] == list(range(35, 86))
    assert alice.get(f"{base}?before_seq=10&after_seq=5").status_code == 400
    assert alice.get(f"{base}?limit=51").status_code == 400


def test_t29_unread_counts_and_read_position(env, alice, bob):
    dm = env.dm(alice, bob)
    for i in range(3):
        env.send(bob, dm, f"hi {i}")

    def unread():
        convs = alice.get("/api/v1/conversations").json()["conversations"]
        return next(c for c in convs if c["id"] == dm)["unread_count"]

    assert unread() == 3
    assert alice.post(f"/api/v1/conversations/{dm}/read", {"seq": 2}).json()["unread_count"] == 1
    assert alice.post(f"/api/v1/conversations/{dm}/read", {"seq": 1}).json()["last_read_seq"] == 2  # never backward
    assert alice.post(f"/api/v1/conversations/{dm}/read", {"seq": 99}).json()["unread_count"] == 0  # capped
    assert unread() == 0


def test_t77_a_failed_send_leaves_nothing_behind(env, alice, bob, monkeypatch):
    dm = env.dm(alice, bob)

    def boom(*a, **k):
        raise RuntimeError("notification step failed")

    monkeypatch.setattr(env.svc.notifications, "create", boom)
    failed = env.send(alice, dm, "hello @bob")
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "internal_error"
    assert "notification step failed" not in failed.text
    assert env.svc.db.scalar("SELECT COUNT(*) FROM messages") == 0
    assert env.svc.db.scalar("SELECT COUNT(*) FROM mentions") == 0
    assert env.svc.db.scalar("SELECT last_seq FROM conversations WHERE id = ?", (dm,)) == 0
    monkeypatch.undo()
    assert env.send(alice, dm, "now it works").json()["message"]["seq"] == 1


def test_t78_times_are_stored_in_utc(env, alice, bob):
    dm = env.dm(alice, bob)
    msg = env.send(alice, dm, "ping @bob").json()["message"]
    assert ISO_Z.match(msg["created_at"])
    db = env.svc.db
    for sql in ("SELECT created_at FROM users", "SELECT created_at FROM conversations",
                "SELECT created_at FROM messages", "SELECT created_at FROM notifications",
                "SELECT joined_at FROM memberships", "SELECT ts FROM audit_log"):
        rows = db.q_all(sql)
        assert rows, sql
        assert all(ISO_Z.match(list(r.values())[0]) for r in rows), sql
    assert ISO_Z.match(env.client.post("/api/v1/auth/dev-login", json={"username": "alice"}).json()["expires_at"])
