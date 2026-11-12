"""Message, attachment, search, and notification routes."""
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel
from starlette.responses import FileResponse, JSONResponse, Response

from app import clock
from app.deps import current_user

router = APIRouter(prefix="/api/v1")


class SendMessage(BaseModel):
    client_msg_id: str
    body: str
    reply_to_id: str | None = None
    attachment_ids: list[str] = []


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    request: Request,
    limit: int | None = Query(None, ge=1, le=50),
    before_seq: int | None = Query(None, ge=0),
    after_seq: int | None = Query(None, ge=0),
    around_seq: int | None = Query(None, ge=0),
    user: dict = Depends(current_user),
):
    return request.app.state.svc.messages.list_messages(
        user["id"], conversation_id, limit, before_seq, after_seq, around_seq
    )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, body: SendMessage, request: Request, user: dict = Depends(current_user)):
    t0 = clock.monotonic()  # the moment the server has the request (SLO-02)
    message, duplicate = request.app.state.svc.messages.send(
        user, conversation_id, body.client_msg_id, body.body, body.reply_to_id, body.attachment_ids, t0
    )
    return JSONResponse({"message": message, "duplicate": duplicate}, status_code=200 if duplicate else 201)


@router.get("/messages/{message_id}/thread")
async def get_thread(message_id: str, request: Request, user: dict = Depends(current_user)):
    return request.app.state.svc.messages.thread(user["id"], message_id)


@router.delete("/messages/{message_id}")
async def delete_message(message_id: str, request: Request, user: dict = Depends(current_user)):
    request.app.state.svc.messages.delete(user, message_id)
    return Response(status_code=204)


@router.post("/attachments")
async def upload_attachment(
    request: Request,
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
):
    svc = request.app.state.svc
    svc.conversations.require_member(user["id"], conversation_id)  # before reading the file
    data = await file.read(svc.attachments.max_bytes + 1)
    stored = svc.attachments.store(user["id"], conversation_id, file.filename or "", file.content_type or "", data)
    return JSONResponse(stored, status_code=201)


@router.get("/attachments/{attachment_id}")
async def download_attachment(attachment_id: str, request: Request, user: dict = Depends(current_user)):
    path, filename, content_type = request.app.state.svc.attachments.open_for(user["id"], attachment_id)
    return FileResponse(
        path, media_type=content_type, filename=filename, content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/search")
async def search(request: Request, q: str = Query(""), limit: int | None = Query(None, ge=1, le=50),
                 user: dict = Depends(current_user)):
    return request.app.state.svc.search.search(user["id"], q, limit)


@router.get("/notifications")
async def list_notifications(request: Request, unread_only: bool = False, user: dict = Depends(current_user)):
    return request.app.state.svc.notifications.list_for(user["id"], unread_only)


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, request: Request, user: dict = Depends(current_user)):
    return request.app.state.svc.notifications.mark_read(user["id"], notification_id)
