"""The ASGI app factory: middleware, error handlers, router registration.

Nothing else. The routes live in `app.api.routes`, the judgement in
`app.services.agent`, the vocabulary in `app.schemas`, the wire format in
`app.a2ui`.

A factory rather than a module-level `app` built by side effect: a test needs to
construct the app after setting its own environment, and `configure_logging` at
import time would install handlers merely because something imported this file.
`app = create_app()` at the bottom is what uvicorn's `app.main:app` target
resolves, and it is the only line here that runs on import.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import register_error_handlers
from app.api.middleware import request_context
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


# FastAPI passes the app to a lifespan handler; this one needs nothing from it.
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    """Report the configuration once, at startup.

    A boot line that names the model and whether a key is present is the fastest
    answer to "why is every section a missing-key fallback".
    """
    settings = get_settings()
    logger.info(
        "starting: model=%s has_api_key=%s origins=%s",
        settings.openai_model,
        settings.has_api_key,
        settings.allowed_origins,
    )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Args:
        settings: Injected configuration. Defaults to the process settings; a test
            passes its own rather than mutating the environment.

    Returns:
        The configured app, with CORS, the request-id middleware, the error
        handlers and the API router installed.
    """
    # The entrypoint is the one place a dotenv load belongs; importing a module for
    # its side effect anywhere else would make import order load-bearing.
    load_dotenv()
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    app = FastAPI(
        title="Signal · Generative UI POC",
        summary="Agent output as design-system molecules, streamed.",
        version="0.1.0",
        lifespan=_lifespan,
    )

    app.add_middleware(BaseHTTPMiddleware, dispatch=request_context)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_error_handlers(app)
    app.include_router(router)

    if settings is not None:
        # The routes depend on `get_settings`, which reads the environment. An
        # explicitly-injected configuration has to displace that or it would be
        # used for CORS here and silently ignored inside every handler -- which is
        # exactly the split a test would not notice until it asserted on a value
        # that came from the developer's own `.env`.
        app.dependency_overrides[get_settings] = lambda: settings

    return app


app = create_app()
