"""Configuration from environment variables (DD-17). Every value has a safe default."""
import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(f"CHATAPP_{name}", default)


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _names(value: str | None, default: tuple) -> tuple:
    if value is None:
        return default
    return tuple(x.strip().lower() for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/chatapp.db"
    attachment_dir: str = "data/attachments"
    secret_key: str | None = None
    dev_auth: bool = True
    admin_usernames: tuple = ("admin1", "admin2")
    seed_users: tuple = ("alice", "bob", "carol")
    session_hours: float = 8
    rate_limit_per_min: int = 30
    max_upload_mb: int = 25
    request_timeout_s: float = 10.0
    retention_days: int = 0
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    # Product limits (A-31, A-23). Kept here so they are visible in one place.
    max_message_chars: int = 4000
    page_size: int = 50
    queue_size: int = 1000
    ack_timeout_s: float = 10.0
    max_group_members: int = 20
    max_channel_members: int = 100
    max_attachments_per_message: int = 5
    unsent_upload_ttl_s: int = 3600
    copilot_enabled: bool = True
    copilot_delay_s: float = 0.3
    copilot_auto_default: bool = True  # new users get replies to everything they write (they can turn it off)
    copilot_auto_join: bool = True  # the assistant joins every group chat and channel
    copilot_private_chat: bool = True  # every user gets a private direct message with the assistant
    copilot_web: bool = True  # live web lookups (weather, time in other places). Only a place name is sent.
    # The language model behind Copilot. "ollama" is a model on this computer: chat text never leaves the machine.
    ai_provider: str = "ollama"  # ollama | azure_openai | none
    ai_model: str = "llama3.2:3b"
    ai_endpoint: str = "http://127.0.0.1:11434"
    ai_api_key: str | None = None
    ai_timeout_s: float = 120.0
    ai_max_tokens: int = 300
    ai_context_messages: int = 12

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        return cls(
            db_path=_env("DB_PATH", d.db_path),
            attachment_dir=_env("ATTACHMENT_DIR", d.attachment_dir),
            secret_key=_env("SECRET_KEY", d.secret_key),
            dev_auth=_bool(_env("DEV_AUTH"), d.dev_auth),
            admin_usernames=_names(_env("ADMIN_USERNAMES"), d.admin_usernames),
            seed_users=_names(_env("SEED_USERS"), d.seed_users),
            session_hours=float(_env("SESSION_HOURS", d.session_hours)),
            rate_limit_per_min=int(_env("RATE_LIMIT_PER_MIN", d.rate_limit_per_min)),
            max_upload_mb=int(_env("MAX_UPLOAD_MB", d.max_upload_mb)),
            request_timeout_s=float(_env("REQUEST_TIMEOUT_S", d.request_timeout_s)),
            retention_days=int(_env("RETENTION_DAYS", d.retention_days)),
            log_level=_env("LOG_LEVEL", d.log_level),
            host=_env("HOST", d.host),
            port=int(_env("PORT", d.port)),
            copilot_enabled=_bool(_env("COPILOT"), d.copilot_enabled),
            copilot_auto_default=_bool(_env("COPILOT_AUTO_DEFAULT"), d.copilot_auto_default),
            copilot_auto_join=_bool(_env("COPILOT_AUTO_JOIN"), d.copilot_auto_join),
            copilot_private_chat=_bool(_env("COPILOT_PRIVATE_CHAT"), d.copilot_private_chat),
            copilot_web=_bool(_env("COPILOT_WEB"), d.copilot_web),
            ai_provider=_env("AI_PROVIDER", d.ai_provider),
            ai_model=_env("AI_MODEL", d.ai_model),
            ai_endpoint=_env("AI_ENDPOINT", d.ai_endpoint),
            ai_api_key=_env("AI_API_KEY", d.ai_api_key),
            ai_timeout_s=float(_env("AI_TIMEOUT_S", d.ai_timeout_s)),
            ai_max_tokens=int(_env("AI_MAX_TOKENS", d.ai_max_tokens)),
        )
