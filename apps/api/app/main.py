"""FastAPI application: routers, error handlers, request ids and security headers."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import dispose_engines
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging, request_id_var
from app.core.storage import ensure_bucket
from app.modules.attendance.router import router as attendance_router
from app.modules.auth.router import me_router
from app.modules.auth.router import router as auth_router
from app.modules.org.router import router as org_router
from app.modules.privacy.router import router as privacy_router
from app.modules.staff.router import router as staff_router
from app.modules.tasks.router import router as tasks_router
from app.policy.deps import assert_all_routes_declared, public

log = logging.getLogger("oglos.api")

_PG_ERRORS = {
    "23505": ("DUPLICATE", 409),
    "23503": ("INVALID_REFERENCE", 422),
    "23514": ("CONSTRAINT_VIOLATION", 422),
    "42501": ("FORBIDDEN_WRITE", 403),
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    assert_all_routes_declared(app)
    if not get_settings().is_production:
        try:
            await asyncio.to_thread(ensure_bucket)
        except Exception:  # storage may start after the API in dev
            log.warning("could not ensure S3 bucket at startup")
    yield
    await dispose_engines()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(
        title="OGLOS API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/api/docs",
        openapi_url=None if settings.is_production else "/api/v1/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "Idempotency-Key",
            "X-Request-ID",
        ],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request_id_var.set(rid[:64])
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid[:64]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    app.add_exception_handler(AppError, app_error_handler)

    @app.exception_handler(IntegrityError)
    async def integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        pgcode = getattr(getattr(exc.orig, "__cause__", None), "sqlstate", None) or getattr(
            exc.orig, "sqlstate", None
        )
        code, status = _PG_ERRORS.get(str(pgcode), ("CONFLICT", 409))
        return JSONResponse(
            status_code=status,
            content={
                "error": {"code": code, "message_key": f"errors.{code.lower()}", "details": {}}
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "type": e["type"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message_key": "errors.validation_failed",
                    "details": {"fields": fields},
                }
            },
        )

    api = APIRouter(prefix="/api/v1")

    @api.get("/health", dependencies=[Depends(public())])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    api.include_router(auth_router)
    api.include_router(me_router)
    api.include_router(org_router)
    api.include_router(staff_router)
    api.include_router(tasks_router)
    api.include_router(attendance_router)
    api.include_router(privacy_router)
    app.include_router(api)
    return app


app = create_app()
