"""Request-scoped concerns: a correlation id, and how long the request took.

Middleware, not a decorator on each route, because these have to hold for the
streaming endpoints too -- and a streamed response is where a correlation id
earns its keep, since one request's log lines are spread over seconds.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

_Next = Callable[[Request], Awaitable[Response]]


async def request_context(request: Request, call_next: _Next) -> Response:
    """Attach a request id to the log context and echo it back on the response.

    An inbound `X-Request-ID` is honoured so a trace started at the proxy carries
    through; otherwise one is minted here. The value is echoed on the response so
    a user reporting a bad render can be matched to the run that produced it.
    """
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    # Bounded and stripped of anything that could forge a log line: this value is
    # interpolated into every record for the life of the request.
    request_id = incoming[:64] if incoming.isalnum() else uuid4().hex[:12]

    token = request_id_var.set(request_id)
    started = time.monotonic()
    try:
        response = await call_next(request)
        # Logged before the reset, or this line would carry no id at all -- the
        # streaming routes are the ones that need it most, and they return here as
        # soon as the headers are ready. The response body still sees the id: the
        # generator captured this context when it was created.
        elapsed_ms = int((time.monotonic() - started) * 1000)
        # For a stream that figure is time-to-first-byte, not the full duration.
        # The stream's own timing is measured by the agent's clock and reported in
        # its `meta` event.
        logger.info(
            "%s %s -> %s in %sms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    finally:
        request_id_var.reset(token)

    response.headers[REQUEST_ID_HEADER] = request_id
    return response
