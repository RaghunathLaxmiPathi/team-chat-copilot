"""T-24, T-36 to T-39: mentions, search, and notifications."""
from pathlib import Path


def test_t24_mentions_create_notifications_without_message_text(env, alice, bob, carol):
    group = env.group(alice, "Team", bob)  # carol is not a member
    env.send(alice, group, "ping @bob and @carol and @nobody_here secretphrase")
    mine = bob.get("/api/v1/notifications").json()
    mentions = [n for n in mine["notifications"] if n["type"] == "mention"]
    assert len(mentions) == 1 and mentions[0]["actor_name"] == "Alice"
    assert "secretphrase" not in str(mine)
    assert [n for n in carol.get("/api/v1/notifications").json()["notifications"] if n["type"] == "mention"] == []
    # Email-style entries are queued without text for the offline person.
    rows = env.svc.db.q_all("SELECT * FROM notification_outbox WHERE type = 'mention'")
    assert len(rows) == 1 and "secretphrase" not in str(rows)


def test_t36_search_is_limited_to_what_the_user_may_see(env, alice, bob, carol):
    shared = env.group(alice, "Shared", bob)
    private = env.dm(alice, carol)
    env.send(alice, shared, "quartz before bob joined? no, bob is here")
    env.send(alice, private, "quartz only for carol")
    late = env.group(alice, "Late", carol)
    env.send(alice, late, "quartz before bob joined")
    alice.post(f"/api/v1/conversations/{late}/members", {"user_id": bob.id})
    env.send(alice, late, "quartz after bob joined")
    gone = env.send(alice, shared, "quartz deleted soon").json()["message"]
    alice.delete(f"/api/v1/messages/{gone['id']}")

    bodies = [r["message"]["body"] for r in bob.get("/api/v1/search?q=quartz").json()["results"]]
    assert sorted(bodies) == sorted(["quartz before bob joined? no, bob is here", "quartz after bob joined"])
    carol_bodies = [r["message"]["body"] for r in carol.get("/api/v1/search?q=quartz").json()["results"]]
    assert "quartz only for carol" in carol_bodies and "quartz after bob joined" in carol_bodies
    assert all("deleted soon" not in b for b in bodies + carol_bodies)


def test_t37_search_input_is_safe(env, alice, bob):
    dm = env.dm(alice, bob)
    env.send(alice, dm, "apples and oranges")
    for q in ['"apples', "apples AND", "apples OR oranges", "apples*", "NEAR(apples oranges)", "apples -oranges", "a:b"]:
        r = alice.get("/api/v1/search", params={"q": q})
        assert r.status_code == 200, q
    assert alice.get("/api/v1/search", params={"q": "apples oranges"}).json()["results"]
    assert alice.get("/api/v1/search", params={"q": "a"}).status_code == 400
    assert alice.get("/api/v1/search", params={"q": "x" * 101}).status_code == 400
    assert alice.get("/api/v1/search", params={"q": "!!"}).json()["results"] == []


def test_t38_notification_list_and_read(env, alice, bob, carol):
    group = env.group(alice, "G", bob)
    env.send(alice, group, "hi @bob")
    listed = bob.get("/api/v1/notifications").json()
    assert listed["unread_count"] == 2  # added + mention
    first = listed["notifications"][0]
    assert carol.post(f"/api/v1/notifications/{first['id']}/read").status_code == 404
    assert bob.post(f"/api/v1/notifications/{first['id']}/read").json()["read"] is True
    assert bob.post(f"/api/v1/notifications/{first['id']}/read").status_code == 200  # idempotent
    after = bob.get("/api/v1/notifications").json()
    assert after["unread_count"] == 1
    assert len(bob.get("/api/v1/notifications?unread_only=true").json()["notifications"]) == 1


def test_t39_added_notification_and_outbox_entry(env, alice, bob):
    group = env.group(alice, "Crew", bob)
    n = bob.get("/api/v1/notifications").json()["notifications"]
    assert [x["type"] for x in n] == ["added"] and n[0]["conversation_name"] == "Crew"
    rows = env.svc.db.q_all("SELECT * FROM notification_outbox WHERE user_id = ?", (bob.id,))
    assert len(rows) == 1 and rows[0]["channel"] == "email" and rows[0]["sent_at"] is None
    assert set(rows[0]) == {"id", "user_id", "channel", "type", "conversation_id", "actor_id", "created_at", "sent_at"}
