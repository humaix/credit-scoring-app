"""FastAPI application factory for the credit-scoring product API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .db import init_db
from .errors import ApiError
from .routers import (
    applications, assessment, auth, consent, employment, meta, scoring,
    verification,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    yield


def _error(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or []}},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Alternative Credit Scoring API",
        description=(
            "Demo API wrapping the existing XGBoost + SHAP explainability engine. "
            "Identity verification and data-provider integrations are clearly "
            "labelled simulated prototypes."
        ),
        version="1.0.0",
        lifespan=_lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Session-Token"],
    )

    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError):
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            field = ".".join(str(part) for part in err.get("loc", [])[1:])
            details.append({
                # model-level (cross-field) errors carry no field path
                "field": field or "__all__",
                "issue": err.get("msg", ""),
            })
        return _error(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        # never leak internals or stack traces to the client
        return _error(500, "internal_error", "An unexpected error occurred")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "alternative-credit-scoring-api"}

    app.include_router(auth.router)
    app.include_router(applications.router)
    app.include_router(verification.router)
    app.include_router(employment.router)
    app.include_router(consent.router)
    app.include_router(assessment.router)
    app.include_router(scoring.router)
    app.include_router(meta.router)
    return app


app = create_app()
