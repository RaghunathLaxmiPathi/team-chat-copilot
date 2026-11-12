"""Shared test helpers. Each test gets a fresh service, database, and attachment folder."""
import dataclasses
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

logging.getLogger("httpx").setLevel(logging.WARNING)


def make_settings(tmp_path, **overrides) -> Settings:
    base = Settings(
        db_path=str(tmp_path / "chat.db"),
        attachment_dir=str(tmp_path / "attachments"),
        secret_key="test-secret",
        dev_auth=True,
        admin_usernames=("admin1", "admin2"),
        seed_users=("alice", "bob", "carol"),
        # Most tests expect the assistant to stay quiet unless asked. Tests that cover
        # "reply to everything" and auto-join switch these on themselves.
        copilot_auto_default=False,
        copilot_auto_join=False,
        copilot_private_chat=False,
        copilot_web=False,  # tests never reach the internet; web tests plug in a stand-in
        ai_provider="none",  # tests never call a model; AI tests plug in a stand-in
    )
    return dataclasses.replace(base, **overrides)


class Session:
    """A signed-in user: wraps the test client with the user's token."""

    def __init__(self, client: TestClient, token: str, user: dict):
        self.client, self.token, self.user = client, token, user
        self.id = user["id"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, json=None, **kw):
        return self.client.post(path, json=json, headers=self.headers, **kw)

    def patch(self, path, json=None, **kw):
        return self.client.patch(path, json=json, headers=self.headers, **kw)

    def delete(self, path, **kw):
        return self.client.delete(path, headers=self.headers, **kw)

    def upload(self, conversation_id: str, filename: str, data: bytes, content_type: str):
        return self.client.post(
            "/api/v1/attachments",
            data={"conversation_id": conversation_id},
            files={"file": (filename, data, content_type)},
            headers=self.headers,
        )

    def ws(self):
        return self.client.websocket_connect(f"/ws?token={self.token}")


class Env:
    def __init__(self, app, client: TestClient, settings: Settings):
        self.app, self.client, self.settings = app, client, settings
        self.svc = app.state.svc
        self._counter = 0

    def login(self, username: str) -> Session:
        r = self.client.post("/api/v1/auth/dev-login", json={"username": username})
        assert r.status_code == 200, r.text
        body = r.json()
        return Session(self.client, body["token"], body["user"])

    def new_user(self, admin: Session, username: str, is_admin: bool = False) -> Session:
        r = admin.post("/api/v1/users", {"username": username, "display_name": username.capitalize(), "is_admin": is_admin})
        assert r.status_code == 201, r.text
        return self.login(username)

    def cid(self) -> str:
        self._counter += 1
        return f"client-msg-{self._counter:06d}"

    def send(self, who: Session, conversation_id: str, body: str, **extra):
        payload = {"client_msg_id": self.cid(), "body": body, **extra}
        return who.post(f"/api/v1/conversations/{conversation_id}/messages", payload)

    def dm(self, a: Session, b: Session) -> str:
        r = a.post("/api/v1/conversations", {"type": "dm", "member_ids": [b.id]})
        assert r.status_code in (200, 201), r.text
        return r.json()["id"]

    def group(self, creator: Session, name: str, *members: Session) -> str:
        r = creator.post("/api/v1/conversations", {"type": "group", "name": name, "member_ids": [m.id for m in members]})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def channel(self, admin: Session, name: str, *members: Session) -> str:
        r = admin.post("/api/v1/conversations", {"type": "channel", "name": name, "member_ids": [m.id for m in members]})
        assert r.status_code == 201, r.text
        return r.json()["id"]


def _build(tmp_path, **overrides):
    settings = make_settings(tmp_path, **overrides)
    app = create_app(settings, start_background=False)
    # One shared event loop for every request and socket, as in production.
    with TestClient(app) as client:
        yield Env(app, client, settings)
    app.state.svc.db.close()


@pytest.fixture
def env(tmp_path, request):
    # Tests marked @pytest.mark.fast get a high send limit (for tests that send many messages).
    fast = request.node.get_closest_marker("fast") is not None
    yield from _build(tmp_path, **({"rate_limit_per_min": 100000} if fast else {}))


@pytest.fixture
def alice(env):
    return env.login("alice")


@pytest.fixture
def bob(env):
    return env.login("bob")


@pytest.fixture
def carol(env):
    return env.login("carol")


@pytest.fixture
def admin(env):
    return env.login("admin1")
