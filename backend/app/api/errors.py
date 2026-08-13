"""The one place an exception becomes a status code.

Registered on the app in `app.main`. Services raise `AppError` subclasses and
know nothing about HTTP; routes never build an error body by hand.

The streaming endpoints mostly cannot use these -- once the response has started
there is no status code left to change, so `app.services.agent` renders its
failures as a molecule instead. This covers the non-streaming routes and anything
that fails before the first byte.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.schemas import ErrorResponse
from app.errors import AppError

logger = logging.getLogger(__name__)


# Starlette calls a handler with `(request, exc)`; both names are part of that
# contract even where one is unused.
async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    """Map a deliberate application error to a 400, with a generic body."""
    logger.warning("app error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=type(exc).__name__,
            detail="The request could not be completed.",
        ).model_dump(),
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    """Last resort. Log the traceback; tell the client nothing about it."""
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            detail="Something went wrong. The server log has the details.",
        ).model_dump(),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install the handlers. Called once, by the app factory."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(Exception, _handle_unexpected)
