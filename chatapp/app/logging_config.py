"""Structured JSON logs. Only whitelisted fields are ever written (DD-21, PRV-03)."""
import json
import logging
import re
import sys

ALLOWED_EXTRA = (
    "request_id", "method", "path", "status", "duration_ms", "user_id",
    "event", "conn_id", "code", "count",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ALLOWED_EXTRA:
            if hasattr(record, key):
                out[key] = getattr(record, key)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


class RedactTokens(logging.Filter):
    """The real-time address carries the session token. The web server logs that address itself,
    so every log line passes through here and the token is blanked out (risk R-12)."""

    _TOKEN = re.compile(r"(token=)[^\s\"&']+")

    def filter(self, record: logging.LogRecord) -> bool:
        text = record.getMessage()
        if "token=" in text:
            record.msg = self._TOKEN.sub(r"\1REDACTED", text)
            record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not any(getattr(h, "_chatapp", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RedactTokens())
        handler._chatapp = True
        root.addHandler(handler)
    # The server's own access log prints full addresses, including query strings.
    # We write our own request log without query strings instead.
    access = logging.getLogger("uvicorn.access")
    access.disabled = True
    access.propagate = False
