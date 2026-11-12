"""Health, readiness, metrics, and objectives (OPS-01, SLO-03)."""
import time

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import JSONResponse

from app.deps import require_admin
from app.errors import ValidationFailed
from app.slo import WINDOWS_MINUTES

router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request):
    try:
        request.app.state.svc.db.scalar("SELECT 1")
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ready"}


@router.get("/metrics")
async def metrics(request: Request, admin: dict = Depends(require_admin)):
    svc = request.app.state.svc
    return {
        "uptime_seconds": round(time.monotonic() - svc.started_at, 1),
        "http": {"requests_total": svc.stats.total, "by_status": svc.stats.by_status},
        "websocket": svc.hub.stats(),
        "storage": {
            "database_bytes": svc.db.size_bytes(),
            "attachment_bytes": svc.attachments.total_bytes(),
            "messages_total": svc.db.scalar("SELECT COUNT(*) FROM messages"),
        },
    }


@router.get("/api/v1/slo")
async def slo(request: Request, window: str | None = Query(None), admin: dict = Depends(require_admin)):
    if window is not None and window not in WINDOWS_MINUTES:
        raise ValidationFailed("window must be 1h, 24h, or 28d.")
    return request.app.state.svc.slo.report(window)
