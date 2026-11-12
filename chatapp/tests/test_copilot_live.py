"""T-98 to T-102: live data (time in any place, weather, who is online, service status)."""
import pytest

from app.realtime_data import RealtimeData
from tests.test_copilot import bot_id, wait_for_count


class FakeWeb(RealtimeData):
    """Stands in for the internet. Records exactly what would have been sent out."""

    def __init__(self, enabled=True):
        super().__init__(enabled)
        self.calls = []

    def run(self, lookup):
        self.calls.append((lookup.kind, lookup.place))
        return f"FAKE {lookup.kind} for {lookup.place}"


@pytest.fixture
def live(env):
    env.svc.copilot.web = FakeWeb()
    return env


def ask_group(env, user, group, text):
    from tests.test_copilot import messages
    before = len(messages(user, group))
    env.send(user, group, "@copilot " + text)
    return wait_for_count(user, group, before + 2)[-1]["body"]


def setup_group(env, creator, *others):
    group = env.group(creator, "Live", *others)
    creator.post(f"/api/v1/conversations/{group}/members", {"user_id": bot_id(env)})
    return group


def test_t98_time_in_other_places_works_offline(live, alice, bob):
    group = setup_group(live, alice, bob)
    reply = ask_group(live, alice, group, "time in Tokyo")
    assert "Asia/Tokyo" in reply and "JST" in reply
    assert "Asia/Kolkata" in ask_group(live, alice, group, "time in Asia/Kolkata")
    assert "UTC" in ask_group(live, alice, group, "time")
    assert live.svc.copilot.web.calls == []  # nothing went to the internet


def test_t99_weather_sends_only_a_place_name_off_the_server(live, alice, bob):
    group = setup_group(live, alice, bob)
    reply = ask_group(live, alice, group, "weather in Seattle")
    assert "FAKE weather for Seattle" in reply
    assert ask_group(live, alice, group, "weather").endswith("Tell me where, for example: weather in Seattle")
    # Unknown time zones are looked up by place name only.
    assert "FAKE time for Atlantis" in ask_group(live, alice, group, "time in Atlantis")
    assert live.svc.copilot.web.calls == [("weather", "Seattle"), ("time", "Atlantis")]


def test_t100_web_lookups_can_be_switched_off(env, alice, bob):
    env.svc.copilot.web = FakeWeb(enabled=False)
    group = setup_group(env, alice, bob)
    assert "switched off" in ask_group(env, alice, group, "weather in Seattle")
    assert "do not know the time zone" in ask_group(env, alice, group, "time in Atlantis")
    assert env.svc.copilot.web.calls == []


def test_t101_who_is_online_uses_live_connections(live, alice, bob, carol):
    group = setup_group(live, alice, bob)  # carol is not in this group
    assert "Nobody" in ask_group(live, alice, group, "who is online")
    with bob.ws() as ws_bob, carol.ws() as ws_carol:
        assert ws_bob.receive_json()["type"] == "hello" and ws_carol.receive_json()["type"] == "hello"
        reply = ask_group(live, alice, group, "who is online")
        assert reply.endswith("Online right now in this conversation: Bob.")  # not Carol: not in this chat
        assert "Carol" not in reply
    assert "Nobody" in ask_group(live, alice, group, "who is online")  # after they leave


def test_t102_service_status_is_for_administrators(live, admin, alice):
    group = live.group(alice, "Ops", admin)
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": bot_id(live)})
    assert "for administrators" in ask_group(live, alice, group, "status")
    reply = ask_group(live, admin, group, "status")
    assert "Live service status:" in reply and "Open connections" in reply and "success rate" in reply
