"""The real-time channel (FR-40, FR-45). Protocol: see the architecture document, section 7."""
import asyncio
import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app import clock
from app.errors import Unauthorized
from app.hub import CLOSE_DEACTIVATED, CLOSE_EXPIRED

router = APIRouter()
log = logging.getLogger("chatapp.ws")


@router.websocket("/ws")
async def realtime(websocket: WebSocket):
    svc = websocket.app.state.svc
    hub = svc.hub
    await websocket.accept()

    # Custom close codes can only be sent after accepting. Token or access refusals are
    # client errors and are not counted against the Success Rate (AR-01).
    try:
        payload = svc.tokens.verify(websocket.query_params.get("token", ""))
    except Unauthorized:
        await websocket.close(code=CLOSE_EXPIRED)
        return
    user = svc.users.get(payload["sub"])
    if not user:
        await websocket.close(code=CLOSE_EXPIRED)
        return
    if user["status"] != "active":
        await websocket.close(code=CLOSE_DEACTIVATED)
        return

    conn = hub.register(websocket, user["id"], payload["exp"])
    writer = asyncio.create_task(hub.run_writer(conn))
    hub.enqueue(conn, {"type": "hello", "user_id": user["id"], "conn_id": conn.id, "server_time": clock.iso()})
    svc.slo.record_request(ok=True)
    try:
        while True:
            try:
                frame = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except ValueError:
                hub.enqueue(conn, {"type": "error", "code": "validation_error", "message": "Frame is not valid JSON."})
                continue
            if not isinstance(frame, dict):
                hub.enqueue(conn, {"type": "error", "code": "validation_error", "message": "Frame must be an object."})
                continue
            kind = frame.get("type")
            if kind == "ping":
                hub.enqueue(conn, {"type": "pong"})
            elif kind == "ack":
                hub.handle_ack(conn, str(frame.get("message_id", "")))
            elif kind == "resume":
                cursors, since = frame.get("cursors"), frame.get("since")
                if not isinstance(cursors, dict) or (since is not None and not hub.valid_time(since)) or not all(
                    isinstance(k, str) and isinstance(v, int) and v >= 0 for k, v in cursors.items()
                ):
                    hub.enqueue(conn, {"type": "error", "code": "validation_error", "message": "Invalid resume frame."})
                    continue
                try:
                    hub.resume(conn, cursors, since)
                except Exception:
                    log.exception("resume_failed", extra={"conn_id": conn.id, "user_id": user["id"]})
                    svc.slo.record_request(ok=False)
                    hub.enqueue(conn, {"type": "error", "code": "internal_error", "message": "Could not resume."})
            else:
                hub.enqueue(conn, {"type": "error", "code": "validation_error", "message": "Unknown frame type."})
    except RuntimeError:
        pass  # the writer already closed the socket (for example, session expired)
    finally:
        hub.unregister(conn)
        writer.cancel()
