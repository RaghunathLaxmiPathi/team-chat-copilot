"""Sign-in, current user, and administration routes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

from app import clock
from app.deps import current_user, require_admin
from app.errors import NotFound, Unauthorized
from app.serializers import public_user

router = APIRouter(prefix="/api/v1")


class DevLogin(BaseModel):
    username: str


class CreateUser(BaseModel):
    username: str
    display_name: str
    is_admin: bool = False


class PatchUser(BaseModel):
    is_admin: bool


class PatchMe(BaseModel):
    copilot_auto: bool | None = None
    copilot_history: bool | None = None


@router.post("/auth/dev-login")
async def dev_login(body: DevLogin, request: Request):
    svc = request.app.state.svc
    if not svc.settings.dev_auth:
        raise NotFound()
    user = svc.users.get_by_username(body.username.strip().lower())
    if not user or user["status"] != "active" or user["is_bot"]:
        raise Unauthorized("Sign-in failed.")
    token, exp = svc.tokens.issue(user["id"])
    return {
        "token": token,
        "expires_at": clock.iso(datetime.fromtimestamp(exp, timezone.utc)),
        "user": public_user(user),
    }


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.patch("/me")
async def patch_me(body: PatchMe, request: Request, user: dict = Depends(current_user)):
    return request.app.state.svc.users.set_copilot_prefs(user["id"], body.copilot_auto, body.copilot_history)


@router.get("/users")
async def list_users(request: Request, user: dict = Depends(current_user)):
    return {"users": request.app.state.svc.users.list_all()}


@router.post("/users")
async def create_user(body: CreateUser, request: Request, admin: dict = Depends(require_admin)):
    created = request.app.state.svc.users.create(admin["id"], body.username, body.display_name, body.is_admin)
    request.app.state.svc.copilot.ensure_private_chat(created["id"])
    return JSONResponse(created, status_code=201)


@router.patch("/users/{user_id}")
async def patch_user(user_id: str, body: PatchUser, request: Request, admin: dict = Depends(require_admin)):
    return request.app.state.svc.users.set_admin(admin["id"], user_id, body.is_admin)


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    return request.app.state.svc.users.deactivate(admin["id"], user_id)
