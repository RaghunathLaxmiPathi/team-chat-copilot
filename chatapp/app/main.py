"""Application assembly: services, middleware, routes, and background jobs."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse, JSONResponse

from app import routes_auth_users, routes_conversations, routes_messages, routes_ops, routes_ws
from app.attachments import AttachmentService
from app.audit import AuditLog
from app.config import Settings
from app.conversations import ConversationService
from app.copilot import CopilotService
from app.db import Database
from app.errors import AppError
from app.hub import ConnectionHub
from app.logging_config import configure_logging
from app.messages import MessageService
from app.middleware import HttpStats, RequestContextMiddleware
from app.notifications import NotificationService
from app.ratelimit import RateLimiter
from app.retention import RetentionService
from app.search import SearchService
from app.security import TokenService, load_or_create_secret
from app.slo import SloTracker
from app.users import UserService

log = logging.getLogger("chatapp")
STATIC_DIR = Path(__file__).parent / "static"


class Services:
    """Everything the routes need, built once per application."""

    def __init__(self, settings: Settings, scanner=None):
        self.settings = settings
        self.started_at = time.monotonic()
        self.stats = HttpStats()
        self.db = Database(settings.db_path)
        self.tokens = TokenService(load_or_create_secret(settings.secret_key, settings.db_path), settings.session_hours)
        self.slo = SloTracker(self.db)
        self.audit = AuditLog(self.db)
        self.rate = RateLimiter(settings.rate_limit_per_min)
        self.hub = ConnectionHub(self.db, settings, self.slo)
        self.notifications = NotificationService(self.db, self.hub)
        self.users = UserService(self.db, self.audit, self.hub, settings.copilot_auto_default)
        self.conversations = ConversationService(self.db, settings, self.audit, self.notifications, self.hub)
        self.attachments = AttachmentService(self.db, settings, self.conversations, scanner)
        self.messages = MessageService(
            self.db, settings, self.conversations, self.attachments, self.notifications, self.rate, self.hub
        )
        self.search = SearchService(self.db)
        self.copilot = CopilotService(self.db, settings, self.conversations, self.messages, self.search,
                                      self.hub, self.slo)
        self.messages.assistant = self.copilot
        self.conversations.bot_provider = self.copilot.bot
        self.conversations.auto_join_bot = settings.copilot_auto_join
        self.retention = RetentionService(self.db, self.messages, settings)
        self.hub.messages = self.messages
        self.hub.conversations = self.conversations


async def _background(svc: Services) -> None:
    """Housekeeping: confirm timeouts, save objectives, clean unsent uploads, apply retention."""
    tick = 0
    while True:
        await asyncio.sleep(5)
        tick += 5
        try:
            svc.hub.sweep()
            if tick % 60 == 0:
                svc.slo.flush()
            if tick % 600 == 0:
                svc.attachments.cleanup_unsent()
            if tick % 3600 == 0:
                svc.retention.purge()
        except Exception:
            log.exception("background_job_failed")


def create_app(settings: Settings | None = None, scanner=None, start_background: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    svc = Services(settings, scanner)
    svc.users.seed(settings.admin_usernames, settings.seed_users)
    svc.copilot.ensure_user()
    svc.copilot.join_existing()
    svc.slo.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_background(svc)) if start_background else None
        yield
        if task:
            task.cancel()
        svc.slo.flush()

    app = FastAPI(title="Team Chat", version="1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.svc = svc
    app.add_middleware(RequestContextMiddleware, slo=svc.slo, settings=settings, stats=svc.stats)

    def _error(request: Request, status: int, code: str, message: str, headers: dict | None = None):
        rid = getattr(request.state, "request_id", "")
        return JSONResponse({"error": {"code": code, "message": message, "request_id": rid}},
                            status_code=status, headers=headers)

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return _error(request, exc.status, exc.code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Report where and what, never the input itself (it could be message text).
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
        return _error(request, 400, "validation_error", f"{where or 'request'}: {first.get('msg', 'invalid')}")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(request, exc.status_code, code, "Not found." if exc.status_code == 404 else str(exc.detail))

    app.include_router(routes_ops.router)
    app.include_router(routes_auth_users.router)
    app.include_router(routes_conversations.router)
    app.include_router(routes_messages.router)
    app.include_router(routes_ws.router)

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
