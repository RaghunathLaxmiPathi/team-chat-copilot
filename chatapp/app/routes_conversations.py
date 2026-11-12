"""Conversation, membership, and read-position routes."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, Response

from app.deps import current_user

router = APIRouter(prefix="/api/v1/conversations")


class CreateConversation(BaseModel):
    type: Literal["dm", "group", "channel"]
    name: str | None = None
    member_ids: list[str] = []


class AddMember(BaseModel):
    user_id: str


class ReadBody(BaseModel):
    seq: int = Field(ge=0)


@router.get("")
async def list_conversations(request: Request, user: dict = Depends(current_user)):
    return {"conversations": request.app.state.svc.conversations.list_for_user(user["id"])}


@router.post("")
async def create_conversation(body: CreateConversation, request: Request, user: dict = Depends(current_user)):
    conversation, created = request.app.state.svc.conversations.create(user, body.type, body.name, body.member_ids)
    return JSONResponse(conversation, status_code=201 if created else 200)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request, user: dict = Depends(current_user)):
    return request.app.state.svc.conversations.get_for_user(user["id"], conversation_id)


@router.post("/{conversation_id}/members")
async def add_member(conversation_id: str, body: AddMember, request: Request, user: dict = Depends(current_user)):
    return request.app.state.svc.conversations.add_member(user, conversation_id, body.user_id)


@router.delete("/{conversation_id}/members/{user_id}")
async def remove_member(conversation_id: str, user_id: str, request: Request, user: dict = Depends(current_user)):
    request.app.state.svc.conversations.remove_member(user, conversation_id, user_id)
    return Response(status_code=204)


@router.post("/{conversation_id}/read")
async def mark_read(conversation_id: str, body: ReadBody, request: Request, user: dict = Depends(current_user)):
    return request.app.state.svc.conversations.mark_read(user["id"], conversation_id, body.seq)
