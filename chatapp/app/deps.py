"""Authentication dependencies. Async on purpose: everything runs on the event loop thread (DD-01)."""
from fastapi import Depends, Request

from app.errors import Forbidden, Unauthorized


async def current_user(request: Request) -> dict:
    """Verify the token and re-check on every request that the user is still active (DD-07, SEC-09)."""
    svc = request.app.state.svc
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise Unauthorized("Sign in to continue.")
    payload = svc.tokens.verify(header[7:].strip())
    user = svc.users.get(payload["sub"])
    if not user or user["status"] != "active" or user["is_bot"]:
        raise Unauthorized("Your session has expired. Sign in again.")
    request.scope.setdefault("state", {})["user_id"] = user["id"]
    return user


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise Forbidden("You are not allowed to do that.")
    return user
