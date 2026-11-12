"""Signed session tokens. Lab stand-in for Entra ID (FR-01, SEC-09, risk R-04)."""
import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path

from app import clock
from app.errors import Unauthorized


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def load_or_create_secret(configured: str | None, db_path: str) -> bytes:
    if configured:
        return configured.encode()
    if db_path == ":memory:":
        return secrets.token_bytes(32)
    key_file = Path(db_path).parent / "secret.key"
    if key_file.exists():
        return key_file.read_text().strip().encode()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    return key.encode()


class TokenService:
    def __init__(self, secret: bytes, session_hours: float):
        self._secret = secret
        self._ttl = int(session_hours * 3600)

    def _sign(self, payload_b64: str) -> str:
        return _b64(hmac.new(self._secret, payload_b64.encode(), hashlib.sha256).digest())

    def issue(self, user_id: str, ttl_seconds: int | None = None) -> tuple[str, float]:
        iat = clock.epoch()
        exp = iat + (self._ttl if ttl_seconds is None else ttl_seconds)
        payload = _b64(json.dumps({"sub": user_id, "iat": iat, "exp": exp}).encode())
        return f"{payload}.{self._sign(payload)}", exp

    def verify(self, token: str) -> dict:
        try:
            payload_b64, signature = token.split(".", 1)
            if not hmac.compare_digest(signature, self._sign(payload_b64)):
                raise ValueError("bad signature")
            payload = json.loads(_unb64(payload_b64))
            if payload["exp"] <= clock.epoch():
                raise ValueError("expired")
            return payload
        except Exception:
            raise Unauthorized("Your session has expired. Sign in again.") from None
