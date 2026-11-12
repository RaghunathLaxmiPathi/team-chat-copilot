"""T-50 to T-59: the real-time channel."""
import pytest
from starlette.websockets import WebSocketDisconnect

from app import clock
from app.hub import CLOSE_DEACTIVATED, CLOSE_EXPIRED, CLOSE_QUEUE_FULL


def frames_until(ws, kind, limit=300):
    """Read frames until one of the given type arrives. Returns it."""
    for _ in range(limit):
        f = ws.receive_json()
        if f["type"] == kind:
            return f
    raise AssertionError(f"no {kind} frame")


def assert_quiet(ws):
    """Nothing else is queued: the next frame answers our ping."""
    ws.send_json({"type": "ping"})
    assert ws.receive_json()["type"] == "pong"


def test_t50_connect_rules(env, admin, alice, carol):
    with alice.ws() as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["user_id"] == alice.id and hello["server_time"].endswith("Z")
    with pytest.raises(WebSocketDisconnect) as bad:
        with env.client.websocket_connect("/ws?token=garbage") as ws:
            ws.receive_json()
    assert bad.value.code == CLOSE_EXPIRED
    old = carol.ws
    admin.post(f"/api/v1/users/{carol.id}/deactivate")
    with pytest.raises(WebSocketDisconnect) as gone:
        with old() as ws:
            ws.receive_json()
    assert gone.value.code == CLOSE_DEACTIVATED


def test_t51_new_messages_are_pushed_to_members_only(env, alice, bob, carol):
    group = env.group(alice, "Team", bob)
    with bob.ws() as ws_bob, carol.ws() as ws_carol:
        ws_bob.receive_json(), ws_carol.receive_json()
        sent = env.send(alice, group, "push me").json()["message"]
        got = frames_until(ws_bob, "message")["message"]
        assert got["id"] == sent["id"] and got["body"] == "push me"
        assert_quiet(ws_carol)  # a non-member gets nothing


def test_t52_the_senders_other_devices_get_the_message(env, alice, bob):
    group = env.group(alice, "Team", bob)
    with alice.ws() as one, alice.ws() as two:
        one.receive_json(), two.receive_json()
        sent = env.send(alice, group, "from my laptop").json()["message"]
        assert frames_until(one, "message")["message"]["id"] == sent["id"]
        assert frames_until(two, "message")["message"]["id"] == sent["id"]


def test_t53_order_is_the_same_for_everyone(env, alice, bob, carol):
    group = env.group(alice, "Trio", bob, carol)
    with bob.ws() as ws_bob, carol.ws() as ws_carol:
        ws_bob.receive_json(), ws_carol.receive_json()
        for i in range(6):
            env.send(alice if i % 2 == 0 else bob, group, f"m{i}")
        seen_bob = [frames_until(ws_bob, "message")["message"]["seq"] for _ in range(6)]
        seen_carol = [frames_until(ws_carol, "message")["message"]["seq"] for _ in range(6)]
    assert seen_bob == seen_carol == [1, 2, 3, 4, 5, 6]


@pytest.mark.fast
def test_t54_resume_replays_in_order_in_pages(env, alice, bob):
    group = env.group(alice, "Busy", bob)
    for i in range(1, 121):
        env.send(alice, group, f"n{i}")
    with bob.ws() as ws:
        ws.receive_json()
        ws.send_json({"type": "resume", "cursors": {group: 0}, "since": None})
        page = frames_until(ws, "resume_page")
        assert [m["seq"] for m in page["messages"]] == list(range(1, 51)) and page["has_more"] is True
        assert frames_until(ws, "resume_done")["server_time"].endswith("Z")
    rest = bob.get(f"/api/v1/conversations/{group}/messages?after_seq=50").json()
    assert [m["seq"] for m in rest["messages"]] == list(range(51, 101)) and rest["has_more_after"] is True


def test_t55_resume_reports_deletions_made_while_offline(env, alice, bob):
    group = env.group(alice, "Team", bob)
    msg = env.send(alice, group, "oops").json()["message"]
    with bob.ws() as ws:
        last_sync = ws.receive_json()["server_time"]
    alice.delete(f"/api/v1/messages/{msg['id']}")
    with bob.ws() as ws:
        ws.receive_json()
        ws.send_json({"type": "resume", "cursors": {group: 1}, "since": last_sync})
        done = frames_until(ws, "resume_done")
    assert done["deleted"] == [{"conversation_id": group, "message_id": msg["id"]}]


def test_t56_deactivation_closes_live_connections(env, admin, alice, carol):
    with carol.ws() as ws:
        ws.receive_json()
        admin.post(f"/api/v1/users/{carol.id}/deactivate")
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == CLOSE_DEACTIVATED


def test_t57_removal_stops_delivery(env, admin, alice, bob):
    channel = env.channel(admin, "News", alice, bob)
    with bob.ws() as ws:
        ws.receive_json()
        assert admin.delete(f"/api/v1/conversations/{channel}/members/{bob.id}").status_code == 204
        assert frames_until(ws, "conversation_removed")["conversation_id"] == channel
        env.send(alice, channel, "bob should not see this")
        assert_quiet(ws)


class FakeSocket:
    async def send_json(self, data):
        pass

    async def close(self, code=1000):
        pass


def test_t58_a_slow_client_is_closed_and_others_are_unaffected(env):
    hub = env.svc.hub
    slow = hub.register(FakeSocket(), "u1", clock.epoch() + 100)
    fine = hub.register(FakeSocket(), "u2", clock.epoch() + 100)
    for i in range(env.settings.queue_size + 5):
        hub.publish_to_users(["u1"], {"type": "message", "n": i})
    assert slow.close_code == CLOSE_QUEUE_FULL
    hub.publish_to_users(["u2"], {"type": "message", "n": 1})
    assert fine.close_code is None and fine.queue.qsize() == 1
    hub.unregister(slow), hub.unregister(fine)


def test_t59_expired_sessions_are_closed(env):
    hub = env.svc.hub
    conn = hub.register(FakeSocket(), "u1", clock.epoch() + 5)
    hub.sweep(now_epoch=clock.epoch())
    assert conn.close_code is None
    hub.sweep(now_epoch=clock.epoch() + 10)
    assert conn.close_code == CLOSE_EXPIRED
    hub.unregister(conn)
