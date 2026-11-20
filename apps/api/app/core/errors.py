"""API errors: a machine code plus an i18n message key that the UI translates."""

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self, code: str, status: int = 400, message_key: str | None = None, **details: Any
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.message_key = message_key or f"errors.{code.lower()}"
        self.details = details


def not_found(entity: str = "resource") -> AppError:
    # Cross-tenant and missing ids both return 404 so ids never leak between hospitals.
    return AppError("NOT_FOUND", 404, "errors.not_found", entity=entity)


def forbidden() -> AppError:
    return AppError("FORBIDDEN", 403, "errors.forbidden")


def unauthorized(code: str = "UNAUTHENTICATED") -> AppError:
    return AppError(code, 401)


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - registered only for AppError
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {"code": exc.code, "message_key": exc.message_key, "details": exc.details}
        },
    )
