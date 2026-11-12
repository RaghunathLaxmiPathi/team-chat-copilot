"""One error type with a stable code and a plain message (DD-20)."""


class AppError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str, *, code: str | None = None, headers: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.headers = headers or {}


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class Forbidden(AppError):
    status = 403
    code = "forbidden"


class NotFound(AppError):
    status = 404
    code = "not_found"

    def __init__(self, message: str = "Not found."):
        super().__init__(message)


class ValidationFailed(AppError):
    status = 400
    code = "validation_error"


class Conflict(AppError):
    status = 409
    code = "conflict"


class PayloadTooLarge(AppError):
    status = 413
    code = "payload_too_large"


class UnsupportedMedia(AppError):
    status = 415
    code = "unsupported_media_type"


class RateLimited(AppError):
    status = 429
    code = "rate_limited"

    def __init__(self, retry_after: int):
        super().__init__(
            "You are sending too fast. Try again in a few seconds.",
            headers={"Retry-After": str(retry_after)},
        )
