"""FastAPI application factory."""

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from carenote import errors
from carenote.alerts.routes import router as alerts_router
from carenote.audit.routes import router as audit_router
from carenote.auth.routes import router as auth_router
from carenote.config import get_settings
from carenote.fhir.routes import router as fhir_router
from carenote.health.routes import router as health_router
from carenote.metrics.routes import router as metrics_router
from carenote.notes.routes import router as notes_router
from carenote.observability import RequestIdMiddleware, configure_logging
from carenote.patients.routes import router as patients_router
from carenote.pipeline import redaction
from carenote.quality.routes import router as quality_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().env != "test":
        # Loading the NLP model takes a few seconds; do it before the first note arrives.
        threading.Thread(target=redaction.warm_up, daemon=True).start()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    prod = settings.env == "prod"
    app = FastAPI(
        lifespan=lifespan,
        title="CareNote AI",
        version="0.1.0",
        description="Voice documentation for nurses. Demo — synthetic data only.",
        # The interactive docs stay a development tool; the schema is generated at build time.
        docs_url=None if prod else "/docs",
        redoc_url=None,
        openapi_url=None if prod else "/openapi.json",
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(patients_router)
    app.include_router(notes_router)
    app.include_router(fhir_router)
    app.include_router(audit_router)
    app.include_router(metrics_router)
    app.include_router(alerts_router)
    app.include_router(quality_router)
    errors.install(app)

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = errors.document(
                get_openapi(
                    title=app.title,
                    version=app.version,
                    description=app.description,
                    routes=app.routes,
                )
            )
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


app = create_app()
