"""T-01 to T-09: sign-in, users, and administration."""
import pytest

from app.main import create_app
from tests.conftest import make_settings


def test_t01_sign_in_and_profile(env, alice):
    r = env.client.post("/api/v1/auth/dev-login", json={"username": "alice"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["expires_at"].endswith("Z")
    me = alice.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_t02_unknown_and_deactivated_users_cannot_sign_in_same_answer(env, admin, carol):
    unknown = env.client.post("/api/v1/auth/dev-login", json={"username": "nobody"})
    assert admin.post(f"/api/v1/users/{carol.id}/deactivate").status_code == 200
    deactivated = env.client.post("/api/v1/auth/dev-login", json={"username": "carol"})
    assert unknown.status_code == deactivated.status_code == 401
    assert unknown.json()["error"]["message"] == deactivated.json()["error"]["message"]


def test_t03_bad_tokens_are_refused(env, alice):
    good = alice.token
    tampered = good[:-1] + ("A" if good[-1] != "A" else "B")
    expired, _ = env.svc.tokens.issue(alice.id, ttl_seconds=-1)
    for header in (None, "Bearer not-a-token", f"Bearer {tampered}", f"Bearer {expired}", "Basic abc"):
        headers = {"Authorization": header} if header else {}
        r = env.client.get("/api/v1/me", headers=headers)
        assert r.status_code == 401, header
        assert r.json()["error"]["code"] == "unauthorized"


def test_t04_administrators_create_users_and_others_cannot(env, admin, alice):
    ok = admin.post("/api/v1/users", {"username": "dave", "display_name": "Dave"})
    assert ok.status_code == 201
    assert alice.post("/api/v1/users", {"username": "erin", "display_name": "Erin"}).status_code == 403
    assert admin.post("/api/v1/users", {"username": "dave", "display_name": "Dave"}).status_code == 409
    for bad in ("A!", "ab", "UPPER", "has space"):
        assert admin.post("/api/v1/users", {"username": bad, "display_name": "X"}).status_code == 400, bad


def test_t05_at_least_two_administrators_remain(env, admin):
    admin2 = env.login("admin2")
    assert admin.patch(f"/api/v1/users/{admin2.id}", {"is_admin": False}).status_code == 409
    assert admin.post(f"/api/v1/users/{admin2.id}/deactivate").status_code == 409
    env.new_user(admin, "admin3", is_admin=True)
    assert admin.patch(f"/api/v1/users/{admin2.id}", {"is_admin": False}).status_code == 200


def test_t06_deactivation_takes_effect_at_once(env, admin, alice, carol):
    group = env.group(alice, "Team", carol)
    dm = env.dm(alice, carol)
    old_token_headers = carol.headers
    assert admin.post(f"/api/v1/users/{carol.id}/deactivate").status_code == 200
    assert env.client.get("/api/v1/me", headers=old_token_headers).status_code == 401
    members = alice.get(f"/api/v1/conversations/{group}").json()["members"]
    assert [m["id"] for m in members] == [alice.id]
    assert alice.get(f"/api/v1/conversations/{dm}").status_code == 200  # direct message stays


def test_t07_deactivated_authors_show_as_former_members(env, admin, alice, carol):
    dm = env.dm(alice, carol)
    env.send(carol, dm, "I was here")
    admin.post(f"/api/v1/users/{carol.id}/deactivate")
    msgs = alice.get(f"/api/v1/conversations/{dm}/messages").json()["messages"]
    assert msgs[0]["body"] == "I was here"
    assert msgs[0]["sender_status"] == "deactivated"


def test_t08_members_cannot_deactivate_or_change_roles(env, alice, bob):
    assert alice.post(f"/api/v1/users/{bob.id}/deactivate").status_code == 403
    assert alice.patch(f"/api/v1/users/{bob.id}", {"is_admin": True}).status_code == 403


def test_t09_start_up_requires_two_administrators(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(make_settings(tmp_path / "one", admin_usernames=("admin1",)), start_background=False)
    app = create_app(make_settings(tmp_path / "two"), start_background=False)
    assert app.state.svc.users.active_admin_count() == 2
    app.state.svc.db.close()


def test_admin_cannot_deactivate_self(env, admin):
    env.new_user(admin, "admin3", is_admin=True)
    assert admin.post(f"/api/v1/users/{admin.id}/deactivate").status_code == 409
