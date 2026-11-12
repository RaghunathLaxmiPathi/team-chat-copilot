"""T-30 to T-35: attachments."""
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import clock
from app.main import create_app
from tests.conftest import Env, _build, make_settings

PDF = b"%PDF-1.4 hello"


@pytest.fixture
def small(tmp_path):
    yield from _build(tmp_path, max_upload_mb=1)


def test_t30_upload_send_and_download(env, alice, bob):
    dm = env.dm(alice, bob)
    up = alice.upload(dm, "notes.pdf", PDF, "application/pdf")
    assert up.status_code == 201
    att = up.json()
    assert att["filename"] == "notes.pdf" and att["size_bytes"] == len(PDF)
    msg = env.send(alice, dm, "see attached", attachment_ids=[att["id"]]).json()["message"]
    assert [a["id"] for a in msg["attachments"]] == [att["id"]]
    got = bob.get(f"/api/v1/attachments/{att['id']}")
    assert got.status_code == 200 and got.content == PDF
    assert got.headers["content-disposition"].startswith("attachment")
    assert got.headers["x-content-type-options"] == "nosniff"


def test_t31_size_and_type_limits_and_safe_names(small):
    env = small
    alice, bob = env.login("alice"), env.login("bob")
    dm = env.dm(alice, bob)
    assert alice.upload(dm, "big.pdf", b"x" * (1024 * 1024 + 1), "application/pdf").status_code == 413
    assert alice.upload(dm, "edge.pdf", b"x" * (1024 * 1024), "application/pdf").status_code == 201
    assert alice.upload(dm, "tool.exe", b"MZ", "application/octet-stream").status_code == 415
    assert alice.upload(dm, "note.txt", b"hi", "image/png").status_code == 415  # type does not match
    assert alice.upload(dm, "empty.pdf", b"", "application/pdf").status_code == 400
    sneaky = alice.upload(dm, "..\\..\\evil.txt", b"hi", "text/plain")
    assert sneaky.status_code == 201 and sneaky.json()["filename"] == "evil.txt"
    stored = {p.name for p in Path(env.settings.attachment_dir).iterdir()}
    assert all(".." not in n and "evil" not in n for n in stored)


def test_t32_only_members_can_upload_or_open(env, alice, bob, carol):
    dm = env.dm(alice, bob)
    assert carol.upload(dm, "x.pdf", PDF, "application/pdf").status_code == 404
    att = alice.upload(dm, "x.pdf", PDF, "application/pdf").json()
    env.send(alice, dm, "file", attachment_ids=[att["id"]])
    assert carol.get(f"/api/v1/attachments/{att['id']}").status_code == 404
    assert bob.get(f"/api/v1/attachments/{att['id']}").status_code == 200


def test_t33_attachment_rules_when_sending(env, alice, bob):
    dm = env.dm(alice, bob)
    other = env.group(alice, "Other", bob)
    uploads = [alice.upload(dm, f"f{i}.pdf", PDF, "application/pdf").json()["id"] for i in range(6)]
    assert env.send(alice, dm, "six", attachment_ids=uploads).status_code == 400
    assert env.send(alice, dm, "twice", attachment_ids=[uploads[0], uploads[0]]).status_code == 400
    theirs = bob.upload(dm, "b.pdf", PDF, "application/pdf").json()["id"]
    assert env.send(alice, dm, "not mine", attachment_ids=[theirs]).status_code == 400
    assert env.send(alice, other, "wrong place", attachment_ids=[uploads[0]]).status_code == 400
    assert env.send(alice, dm, "ok", attachment_ids=[uploads[0]]).status_code == 201
    assert env.send(alice, dm, "reuse", attachment_ids=[uploads[0]]).status_code == 400
    # An unsent upload can be opened only by the uploader.
    assert alice.get(f"/api/v1/attachments/{uploads[1]}").status_code == 200
    assert bob.get(f"/api/v1/attachments/{uploads[1]}").status_code == 404


def test_t34_unsent_uploads_are_removed_after_an_hour(env, alice, bob):
    dm = env.dm(alice, bob)
    att = alice.upload(dm, "later.pdf", PDF, "application/pdf").json()
    assert env.svc.attachments.cleanup_unsent() == 0
    assert env.svc.attachments.cleanup_unsent(now=clock.now() + timedelta(hours=1, minutes=1)) == 1
    assert alice.get(f"/api/v1/attachments/{att['id']}").status_code == 404
    assert list(Path(env.settings.attachment_dir).iterdir()) == []


def test_t35_the_scanner_can_reject_a_file(tmp_path):
    class RejectBad:
        def scan(self, filename, data):
            return b"EICAR" not in data

    app = create_app(make_settings(tmp_path), scanner=RejectBad(), start_background=False)
    with TestClient(app) as client:
        env = Env(app, client, app.state.svc.settings)
        alice, bob = env.login("alice"), env.login("bob")
        dm = env.dm(alice, bob)
        assert alice.upload(dm, "bad.pdf", b"EICAR test", "application/pdf").status_code == 400
        assert alice.upload(dm, "good.pdf", PDF, "application/pdf").status_code == 201
        assert env.svc.db.scalar("SELECT COUNT(*) FROM attachments") == 1
        assert len(list(Path(env.settings.attachment_dir).iterdir())) == 1
    app.state.svc.db.close()
