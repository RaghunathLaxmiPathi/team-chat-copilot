"""T-71 to T-75: privacy, audit, retention, and backup."""
import logging
import sqlite3
from datetime import timedelta
from pathlib import Path

from app import clock


def test_t71_logs_hold_no_message_text_or_tokens(env, alice, bob, caplog):
    caplog.set_level(logging.DEBUG)
    dm = env.dm(alice, bob)
    att = alice.upload(dm, "marker-file-name.pdf", b"%PDF-1.4", "application/pdf").json()
    env.send(alice, dm, "SECRETMARKER hello @bob", attachment_ids=[att["id"]])
    alice.get("/api/v1/search", params={"q": "SECRETMARKER"})
    with alice.ws() as ws:  # the token is in the address of this connection
        ws.receive_json()
    text = " ".join(
        f"{r.getMessage()} {getattr(r, 'path', '')} {r.__dict__.get('exc', '')}"
        for r in caplog.records if r.name.startswith("chatapp")
    )
    assert "chatapp" in {r.name.split(".")[0] for r in caplog.records}
    for secret in ("SECRETMARKER", "marker-file-name", alice.token):
        assert secret not in text


def test_t71b_the_web_servers_own_log_line_never_shows_a_token():
    """The server logs the real-time address itself, token included. The log filter must blank it."""
    import io
    from app.logging_config import JsonFormatter, RedactTokens

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactTokens())
    logger = logging.getLogger("uvicorn.error")
    logger.addHandler(handler)
    try:
        logger.info('%s - "WebSocket %s" [accepted]', "127.0.0.1:1234", "/ws?token=eyJhbGciOi.secretpart.sig&x=1")
    finally:
        logger.removeHandler(handler)
    line = stream.getvalue()
    assert "secretpart" not in line and "token=REDACTED" in line and "[accepted]" in line


def test_t72_audit_records(env, admin, alice, bob):
    erin = env.new_user(admin, "erin")
    admin.post(f"/api/v1/users/{erin.id}/deactivate")
    group = env.group(alice, "G", bob)
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": env.login("carol").id})
    bob.delete(f"/api/v1/conversations/{group}/members/{bob.id}")
    env.channel(admin, "Chan", alice)
    actions = [r["action"] for r in env.svc.db.q_all("SELECT action FROM audit_log WHERE actor_id != 'system'")]
    for expected in ("user.create", "user.deactivate", "group.create", "member.add", "member.remove", "channel.create"):
        assert expected in actions, expected
    rows = env.svc.db.q_all("SELECT ts, actor_id, target_id, detail FROM audit_log WHERE actor_id != 'system'")
    assert all(r["ts"] and r["actor_id"] and r["target_id"] for r in rows)


def test_t73_no_administrator_route_returns_message_text(env, admin, alice, bob):
    dm = env.dm(alice, bob)
    env.send(alice, dm, "CONFIDENTIALTEXT")
    for path in ("/metrics", "/api/v1/slo", "/api/v1/users"):
        assert "CONFIDENTIALTEXT" not in admin.get(path).text
    assert admin.get(f"/api/v1/conversations/{dm}/messages").status_code == 404  # an administrator is not a member


def test_t74_retention_removes_old_content_and_is_off_by_default(env, alice, bob):
    dm = env.dm(alice, bob)
    up = alice.upload(dm, "old.pdf", b"%PDF-1.4", "application/pdf").json()
    old = env.send(alice, dm, "ancientword plans", attachment_ids=[up["id"]]).json()["message"]
    env.send(bob, dm, "recent note")
    db = env.svc.db
    db.exec("UPDATE messages SET created_at = ? WHERE id = ?", (clock.iso(clock.now() - timedelta(days=40)), old["id"]))
    assert env.svc.retention.purge() == 0  # the default is off
    assert db.scalar("SELECT body FROM messages WHERE id = ?", (old["id"],)) == "ancientword plans"
    assert env.svc.retention.purge(days=30) == 1
    msgs = alice.get(f"/api/v1/conversations/{dm}/messages").json()["messages"]
    assert msgs[0]["deleted"] is True and msgs[1]["body"] == "recent note"
    assert alice.get("/api/v1/search?q=ancientword").json()["results"] == []
    assert list(Path(env.settings.attachment_dir).iterdir()) == []


def test_t75_backup_gives_a_consistent_copy(env, alice, bob, tmp_path):
    dm = env.dm(alice, bob)
    for i in range(5):
        env.send(alice, dm, f"backup me {i}")
    target = tmp_path / "copy" / "backup.db"
    env.svc.db.backup(str(target))
    copy = sqlite3.connect(target)
    assert copy.execute("SELECT COUNT(*) FROM messages WHERE body LIKE 'backup me%'").fetchone()[0] == 5
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    copy.close()
