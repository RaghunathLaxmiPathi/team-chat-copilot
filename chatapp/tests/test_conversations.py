"""T-10 to T-18: conversations and membership."""


def _users(env, admin, count, prefix="u"):
    return [env.new_user(admin, f"{prefix}{i:03d}") for i in range(count)]


def test_t10_direct_message_is_one_per_pair(env, alice, bob):
    first = alice.post("/api/v1/conversations", {"type": "dm", "member_ids": [bob.id]})
    again = bob.post("/api/v1/conversations", {"type": "dm", "member_ids": [alice.id]})
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
    assert alice.post("/api/v1/conversations", {"type": "dm", "member_ids": [alice.id]}).status_code == 400
    assert alice.post("/api/v1/conversations", {"type": "dm", "member_ids": ["unknown"]}).status_code == 400


def test_t11_group_rules_and_limits(env, admin, alice):
    people = _users(env, admin, 21)
    ids = [p.id for p in people]
    assert alice.post("/api/v1/conversations", {"type": "group", "name": "G", "member_ids": []}).status_code == 400
    assert alice.post("/api/v1/conversations", {"type": "group", "name": "G", "member_ids": ids[:1]}).status_code == 201
    assert alice.post("/api/v1/conversations", {"type": "group", "name": "G", "member_ids": ids[:20]}).status_code == 400
    full = alice.post("/api/v1/conversations", {"type": "group", "name": "Full", "member_ids": ids[:19]})
    assert full.status_code == 201 and len(full.json()["members"]) == 20
    # Any member can add, but the limit of 20 holds.
    r = people[0].post(f"/api/v1/conversations/{full.json()['id']}/members", {"user_id": ids[19]})
    assert r.status_code == 409
    small = alice.post("/api/v1/conversations", {"type": "group", "name": "S", "member_ids": ids[:1]}).json()["id"]
    assert people[0].post(f"/api/v1/conversations/{small}/members", {"user_id": ids[5]}).status_code == 200


def test_t13_channel_rules(env, admin, alice):
    assert alice.post("/api/v1/conversations", {"type": "channel", "name": "News", "member_ids": []}).status_code == 403
    ok = admin.post("/api/v1/conversations", {"type": "channel", "name": "News", "member_ids": [alice.id]})
    assert ok.status_code == 201
    assert admin.post("/api/v1/conversations", {"type": "channel", "name": "nEWS", "member_ids": []}).status_code == 409
    people = _users(env, admin, 100)
    channel = env.channel(admin, "Everyone", *people[:99])
    assert admin.get(f"/api/v1/conversations/{channel}").json()["members"].__len__() == 100
    assert admin.post(f"/api/v1/conversations/{channel}/members", {"user_id": people[99].id}).status_code == 409


def test_t14_non_members_and_missing_conversations_look_the_same(env, alice, bob, carol):
    dm = env.dm(alice, bob)
    msg = env.send(alice, dm, "private words").json()["message"]
    real = carol.get(f"/api/v1/conversations/{dm}")
    missing = carol.get("/api/v1/conversations/does-not-exist")
    assert real.status_code == missing.status_code == 404
    assert real.json()["error"]["code"] == missing.json()["error"]["code"]
    assert real.json()["error"]["message"] == missing.json()["error"]["message"]
    assert carol.get(f"/api/v1/conversations/{dm}/messages").status_code == 404
    assert carol.get(f"/api/v1/messages/{msg['id']}/thread").status_code == 404
    assert carol.delete(f"/api/v1/messages/{msg['id']}").status_code == 404
    assert carol.get("/api/v1/search?q=private").json()["results"] == []
    assert env.send(carol, dm, "let me in").status_code == 404


def test_t15_removal_stops_access_at_once(env, alice, bob, carol):
    group = env.group(alice, "Trio", bob, carol)
    env.send(alice, group, "welcome")
    assert carol.delete(f"/api/v1/conversations/{group}/members/{carol.id}").status_code == 204
    assert carol.get(f"/api/v1/conversations/{group}").status_code == 404
    assert carol.get(f"/api/v1/conversations/{group}/messages").status_code == 404
    assert group not in [c["id"] for c in carol.get("/api/v1/conversations").json()["conversations"]]


def test_t16_history_visibility_for_group_and_channel_members(env, admin, alice, bob, carol):
    group = env.group(alice, "Project", bob)
    env.send(alice, group, "one")
    env.send(alice, group, "two")
    assert alice.post(f"/api/v1/conversations/{group}/members", {"user_id": carol.id}).status_code == 200
    env.send(alice, group, "three")
    assert [m["body"] for m in carol.get(f"/api/v1/conversations/{group}/messages").json()["messages"]] == ["three"]
    carol.delete(f"/api/v1/conversations/{group}/members/{carol.id}")
    env.send(alice, group, "four")
    env.send(alice, group, "five")
    alice.post(f"/api/v1/conversations/{group}/members", {"user_id": carol.id})
    env.send(alice, group, "six")
    seen = [m["body"] for m in carol.get(f"/api/v1/conversations/{group}/messages").json()["messages"]]
    assert seen == ["three", "six"]

    channel = env.channel(admin, "Announce", alice)
    env.send(alice, channel, "c1")
    env.send(alice, channel, "c2")
    assert admin.post(f"/api/v1/conversations/{channel}/members", {"user_id": bob.id}).status_code == 200
    assert [m["body"] for m in bob.get(f"/api/v1/conversations/{channel}/messages").json()["messages"]] == ["c1", "c2"]


def test_t17_direct_message_with_a_deactivated_person(env, admin, alice, carol):
    dm = env.dm(alice, carol)
    env.send(carol, dm, "before")
    admin.post(f"/api/v1/users/{carol.id}/deactivate")
    assert [m["body"] for m in alice.get(f"/api/v1/conversations/{dm}/messages").json()["messages"]] == ["before"]
    r = env.send(alice, dm, "hello?")
    assert r.status_code == 409 and r.json()["error"]["code"] == "conversation_closed"


def test_t18_leaving_and_role_rules(env, admin, alice, bob, carol):
    group = env.group(alice, "G", bob, carol)
    assert bob.delete(f"/api/v1/conversations/{group}/members/{bob.id}").status_code == 204
    channel = env.channel(admin, "Chan", alice, bob)
    assert alice.delete(f"/api/v1/conversations/{channel}/members/{bob.id}").status_code == 403
    assert admin.delete(f"/api/v1/conversations/{channel}/members/{bob.id}").status_code == 204
    dm = env.dm(alice, carol)
    assert alice.delete(f"/api/v1/conversations/{dm}/members/{alice.id}").status_code == 400
    assert alice.post(f"/api/v1/conversations/{dm}/members", {"user_id": bob.id}).status_code == 400


def test_administrators_manage_channels_without_reading_them(env, admin, alice, bob):
    admin2 = env.login("admin2")
    channel = env.channel(admin, "Private", alice)
    env.send(alice, channel, "secret plans")
    assert admin2.post(f"/api/v1/conversations/{channel}/members", {"user_id": bob.id}).status_code == 200
    assert admin2.get(f"/api/v1/conversations/{channel}/messages").status_code == 404
