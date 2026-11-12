"""T-87 to T-91: the assistant joins every group and channel and replies to everything (when switched on)."""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import Env, _build, make_settings
from tests.test_copilot import bot_id, messages, wait_for_count


@pytest.fixture
def auto(tmp_path):
    yield from _build(tmp_path, copilot_auto_default=True, copilot_auto_join=True)


def member_names(session, cid):
    return {m["display_name"] for m in session.get(f"/api/v1/conversations/{cid}").json()["members"]}


def test_t87_the_assistant_joins_every_group_and_channel_but_not_direct_messages(auto, admin=None):
    env = auto
    alice, bob, admin = env.login("alice"), env.login("bob"), env.login("admin1")
    group = env.group(alice, "Team", bob)
    channel = env.channel(admin, "General", alice)
    dm = env.dm(alice, bob)
    assert "Copilot" in member_names(alice, group)
    assert "Copilot" in member_names(alice, channel)
    assert member_names(alice, dm) == {"Alice", "Bob"}  # a direct message keeps its two people


def test_t88_it_replies_to_everything_for_people_who_have_it_on(auto):
    env = auto
    alice, bob = env.login("alice"), env.login("bob")
    assert alice.get("/api/v1/me").json()["copilot_auto"] is True
    group = env.group(alice, "Team", bob)
    env.send(alice, group, "good morning team")
    msgs = wait_for_count(alice, group, 2)
    assert msgs[1]["sender_name"] == "Copilot" and msgs[1]["body"].startswith("Hello Alice")
    # Bob turns it off: his messages get no reply, Alice's still do.
    assert bob.patch("/api/v1/me", {"copilot_auto": False}).json()["copilot_auto"] is False
    env.send(bob, group, "I prefer quiet")
    time.sleep(0.8)
    assert len(messages(alice, group)) == 3
    env.send(alice, group, "thanks everyone")
    assert wait_for_count(alice, group, 5)[-1]["body"] == "You're welcome!"


def test_t89_questions_are_answered_from_the_conversation(auto):
    env = auto
    alice, bob = env.login("alice"), env.login("bob")
    group = env.group(alice, "Plan", bob)
    env.send(bob, group, "The roadmap deadline is Friday afternoon")
    wait_for_count(alice, group, 2)  # the assistant notes it
    env.send(alice, group, "when is the roadmap deadline?")
    msgs = wait_for_count(alice, group, 4)
    assert "roadmap deadline is Friday" in msgs[-1]["body"]
    env.send(alice, group, "what is the meaning of life?")
    assert "could not find anything" in wait_for_count(alice, group, 6)[-1]["body"]


def test_t90_existing_groups_get_the_assistant_at_start_up(tmp_path):
    first = create_app(make_settings(tmp_path), start_background=False)
    with TestClient(first) as client:
        env = Env(first, client, first.state.svc.settings)
        alice, bob = env.login("alice"), env.login("bob")
        group = env.group(alice, "Old group", bob)
        assert "Copilot" not in member_names(alice, group)
    first.state.svc.db.close()
    second = create_app(make_settings(tmp_path, copilot_auto_join=True), start_background=False)
    with TestClient(second) as client:
        env = Env(second, client, second.state.svc.settings)
        assert "Copilot" in member_names(env.login("alice"), group)
        assert second.state.svc.db.scalar("SELECT COUNT(*) FROM audit_log WHERE action = 'assistant.join'") == 1
    second.state.svc.db.close()


def test_t91_the_assistant_does_not_count_toward_member_limits(auto):
    env = auto
    admin = env.login("admin1")
    people = [env.new_user(admin, f"member{i:02d}") for i in range(21)]
    group = env.group(people[0], "Full", *people[1:20])  # 19 others plus the creator = 20 people
    assert len(member_names(people[0], group)) == 21  # 20 people and Copilot
    assert people[0].post(f"/api/v1/conversations/{group}/members", {"user_id": people[20].id}).status_code == 409
