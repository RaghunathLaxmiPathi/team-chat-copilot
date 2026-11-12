"""Request pipeline: correlation ID, security headers, timing, logging, SLO recording (DD-14, DD-20, DD-21)."""
import logging
import re
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse

from app import clock

log = logging.getLogger("chatapp.access")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


class HttpStats:
    def __init__(self):
        self.total = 0
        self.by_status: dict[str, int] = {}

    def add(self, status: int) -> None:
        self.total += 1
        self.by_status[str(status)] = self.by_status.get(str(status), 0) + 1


def _is_customer_call(path: str) -> bool:
    # Health, metrics, objectives, and static files are not customer requests.
    return path.startswith("/api/") and path != "/api/v1/slo"


class RequestContextMiddleware:
    def __init__(self, app, slo, settings, stats: HttpStats):
        self.app = app
        self.slo = slo
        self.settings = settings
        self.stats = stats

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = supplied if _REQUEST_ID_RE.match(supplied) else uuid.uuid4().hex
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        path = scope["path"]
        start = clock.monotonic()
        holder = {"status": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                holder["status"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                for key, value in SECURITY_HEADERS.items():
                    headers[key] = value
                if path.startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("unhandled_error", extra={"request_id": request_id, "method": scope["method"], "path": path})
            if holder["status"] is None:
                response = JSONResponse(
                    {"error": {"code": "internal_error",
                               "message": "Something went wrong. We will try again.",
                               "request_id": request_id}},
                    status_code=500,
                )
                await response(scope, receive, send_wrapper)
            holder["status"] = 500

        duration = clock.monotonic() - start
        status = holder["status"] or 500
        self.stats.add(status)
        if _is_customer_call(path):
            failed = status >= 500 or duration > self.settings.request_timeout_s
            if failed or status < 400:  # client errors (4xx) are not counted
                self.slo.record_request(ok=not failed)
        log.info("request", extra={
            "request_id": request_id, "method": scope["method"], "path": path, "status": status,
            "duration_ms": round(duration * 1000, 1), "user_id": state.get("user_id"),
        })
