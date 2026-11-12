"""T-92 to T-97: the assistant's private chat, and use of the person's own history and details."""
import pytest

from tests.conftest import _build
from tests.test_copilot import bot_id, messages, wait_for_count


@pytest.fixture
def private(tmp_path):
    yield from _build(tmp_path, copilot_auto_join=True, copilot_private_chat=True)


def private_chat(session):
    convs = session.get("/api/v1/conversations").json()["conversations"]
    return next(c["id"] for c in convs if c["type"] == "dm" and any(m["display_name"] == "Copilot" for m in c["members"]))


def ask(env, session, cid, text):
    before = len(messages(session, cid))
    env.send(session, cid, text)
    return wait_for_count(session, cid, before + 2)[-1]["body"]


def test_t92_everyone_has_a_private_chat_with_a_welcome(private):
    env = private
    alice, bob = env.login("alice"), env.login("bob")
    for who in (alice, bob):
        msgs = messages(who, private_chat(who))
        assert msgs[0]["sender_name"] == "Copilot" and "I'm Copilot" in msgs[0]["body"]
    assert private_chat(alice) != private_chat(bob)  # separate, readable only by their owner
    assert bob.get(f"/api/v1/conversations/{private_chat(alice)}").status_code == 404
    admin = env.login("admin1")
    erin = env.new_user(admin, "erin")  # new people get one too
    assert messages(erin, private_chat(erin))[0]["sender_name"] == "Copilot"


def test_t93_my_details(private):
    env = private
    alice, bob = env.login("alice"), env.login("bob")
    env.group(alice, "Team", bob)
    reply = ask(env, alice, private_chat(alice), "my details")
    assert "Alice (@alice), member" in reply and "Conversations:" in reply and "may use your history: yes" in reply
    group = env.group(alice, "Other", bob)
    in_group = ask(env, alice, group, "@copilot my details")
    assert "private chat" in in_group and "Alice (@alice)" not in in_group


def test_t94_my_history_lists_only_my_own_messages_across_chats(private):
    env = private
    alice, bob = env.login("alice"), env.login("bob")
    group = env.group(alice, "Plans", bob)
    dm = env.dm(alice, bob)
    env.send(alice, group, "alpha plan for the group")
    env.send(bob, group, "bob says something secret")
    env.send(alice, dm, "beta note to bob")
    reply = ask(env, alice, private_chat(alice), "my history")
    assert "alpha plan for the group" in reply and "in Plans" in reply
    assert "beta note to bob" in reply and "Bob (direct message)" in reply
    assert "bob says something secret" not in reply  # only what Alice wrote


def test_t95_search_covers_all_chats_privately_but_only_this_chat_in_a_group(private):
    env = private
    alice, bob = env.login("alice"), env.login("bob")
    one = env.group(alice, "One", bob)
    two = env.group(alice, "Two", bob)
    env.send(bob, one, "zirconium shipment on monday")
    private_reply = ask(env, alice, private_chat(alice), "search zirconium")
    assert "zirconium shipment" in private_reply and "in One" in private_reply
    group_reply = ask(env, alice, two, "@copilot search zirconium")
    assert "zirconium shipment" not in group_reply and "no messages in this conversation" in group_reply


def test_t96_history_respects_what_the_person_may_see_and_their_choice(private):
    env = private
    alice, bob, carol = env.login("alice"), env.login("bob"), env.login("carol")
    group = env.group(alice, "Late", bob)
    env.send(alice, group, "early kumquat discussion")
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": carol.id})
    env.send(alice, group, "later mango discussion")
    carol_reply = ask(env, carol, private_chat(carol), "search discussion")
    assert "mango" in carol_reply and "kumquat" not in carol_reply  # Carol joined later
    assert carol.patch("/api/v1/me", {"copilot_history": False}).json()["copilot_history"] is False
    assert "switched off" in ask(env, carol, private_chat(carol), "my history")
    assert "switched off" in ask(env, carol, private_chat(carol), "my details")


def test_t97_mentions_unread_and_chats(private):
    env = private
    alice, bob = env.login("alice"), env.login("bob")
    group = env.group(alice, "Crew", bob)
    env.send(bob, group, "hey @alice, can you review this?")
    chat = private_chat(alice)
    assert "Bob in Crew" in ask(env, alice, chat, "my mentions")
    unread = ask(env, alice, chat, "unread")
    assert "Crew: 1" in unread
    assert "Crew (group, 3 members)" in ask(env, alice, chat, "my chats")
