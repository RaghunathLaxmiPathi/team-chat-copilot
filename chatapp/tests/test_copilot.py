"""T-80 to T-86: the built-in assistant."""
import time

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import Env, make_settings


def bot_id(env):
    return env.svc.users.get_by_username("copilot")["id"]


def messages(session, cid):
    return session.get(f"/api/v1/conversations/{cid}/messages").json()["messages"]


def wait_for_count(session, cid, count, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        msgs = messages(session, cid)
        if len(msgs) >= count:
            return msgs
        time.sleep(0.05)
    return messages(session, cid)


def ask_group(env, group, user, text, expected_count):
    env.send(user, group, text)
    return wait_for_count(user, group, expected_count)


def test_t80_direct_message_gets_an_answer(env, alice):
    r = alice.post("/api/v1/conversations", {"type": "dm", "member_ids": [bot_id(env)]})
    assert r.status_code == 201
    dm = r.json()["id"]
    env.send(alice, dm, "help")
    msgs = wait_for_count(alice, dm, 2)
    assert len(msgs) == 2
    assert msgs[1]["sender_name"] == "Copilot" and "summarize" in msgs[1]["body"]
    assert msgs[1]["seq"] == 2


def test_t81_in_a_group_it_answers_only_when_mentioned(env, alice, bob):
    group = env.group(alice, "Team", bob)
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": bot_id(env)})
    env.send(alice, group, "just chatting, no assistant needed")
    time.sleep(0.8)
    assert len(messages(alice, group)) == 1
    msgs = ask_group(env, group, alice, "@copilot members", 3)
    assert msgs[2]["sender_name"] == "Copilot"
    assert msgs[2]["body"].startswith("@alice ") and "Bob" in msgs[2]["body"]


def test_t82_summarize(env, alice, bob):
    group = env.group(alice, "Budget", bob)
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": bot_id(env)})
    env.send(alice, group, "The budget review meeting is tomorrow")
    env.send(bob, group, "Budget numbers look good for the meeting")
    msgs = ask_group(env, group, alice, "@copilot summarize", 4)
    reply = msgs[3]["body"]
    assert "Who spoke" in reply and "Alice" in reply and "Bob" in reply
    assert "budget" in reply and "meeting" in reply


def test_t83_search_looks_only_in_this_conversation(env, alice, bob):
    one = env.group(alice, "One", bob)
    two = env.group(alice, "Two", bob)
    for g in (one, two):
        alice.post(f"/api/v1/conversations/{g}/members", {"user_id": bot_id(env)})
    env.send(alice, two, "zirconium shipment arrives monday")
    first = ask_group(env, one, alice, "@copilot search zirconium", 2)
    assert "no messages in this conversation" in first[-1]["body"]
    assert "zirconium shipment" not in first[-1]["body"]
    second = ask_group(env, two, alice, "@copilot search zirconium", 3)
    assert "zirconium shipment" in second[-1]["body"]


def test_t84_summary_respects_what_the_asker_may_see(env, alice, bob, carol):
    group = env.group(alice, "Late", bob)
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": bot_id(env)})
    env.send(alice, group, "earlier secret kumquat plans")
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": carol.id})
    before = len(messages(carol, group))
    env.send(carol, group, "@copilot summarize")
    msgs = wait_for_count(carol, group, before + 2)
    assert "kumquat" not in msgs[-1]["body"]


def test_t85_assistant_account_rules(env, admin, alice):
    assert env.client.post("/api/v1/auth/dev-login", json={"username": "copilot"}).status_code == 401
    assert admin.post(f"/api/v1/users/{bot_id(env)}/deactivate").status_code == 409
    assert env.svc.users.active_admin_count() == 2
    users = {u["username"]: u for u in alice.get("/api/v1/users").json()["users"]}
    assert users["copilot"]["is_bot"] is True and users["alice"]["is_bot"] is False
    group = env.group(alice, "Bots", admin)
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": bot_id(env)})
    env.send(alice, group, "@copilot time")
    wait_for_count(alice, group, 2)
    db = env.svc.db
    assert db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (bot_id(env),)) == 0
    assert db.scalar("SELECT COUNT(*) FROM notification_outbox WHERE user_id = ?", (bot_id(env),)) == 0


def test_t86_ordinary_chat_gets_a_plain_reply_and_there_are_no_loops(env, alice):
    dm = alice.post("/api/v1/conversations", {"type": "dm", "member_ids": [bot_id(env)]}).json()["id"]
    env.send(alice, dm, "make me a sandwich")
    msgs = wait_for_count(alice, dm, 2)
    assert msgs[1]["body"].startswith("Noted, Alice")
    time.sleep(0.8)
    assert len(messages(alice, dm)) == 2  # the assistant does not answer itself


def test_the_assistant_can_be_turned_off(tmp_path):
    app = create_app(make_settings(tmp_path, copilot_enabled=False), start_background=False)
    with TestClient(app):
        assert app.state.svc.users.get_by_username("copilot") is None
    app.state.svc.db.close()
