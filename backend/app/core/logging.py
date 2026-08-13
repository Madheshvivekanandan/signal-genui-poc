"""Logging configuration and the request-id that ties a run's lines together.

Configured once, from the app factory. Modules take a logger and never touch
handlers or `basicConfig` -- a library that configures logging steals the
decision from whatever embeds it.

The request id exists because this service's interesting failures are streamed:
one request emits a validation warning, a dropped molecule and an upstream
exception across several seconds, interleaved with another request's lines. A
correlation id is the difference between reading that log and guessing at it.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

# Set by the middleware for the life of one request. A ContextVar rather than a
# global so concurrent requests -- and the threadpool the sync routes run in --
# each see their own value.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s"


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every record.

    A filter rather than an adapter at each call site: call sites forget, and a
    format string that references a missing field raises inside the logging
    machinery instead of logging.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    """Install the one handler this service logs through.

    Args:
        level: A level name, e.g. `INFO`. An unrecognised value falls back to
            `INFO` rather than raising -- a typo in an env var should not stop the
            process from booting, but it should be visible in the log.
    """
    resolved = logging.getLevelNamesMapping().get(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(resolved or logging.INFO)

    if resolved is None:
        logging.getLogger(__name__).warning("unknown LOG_LEVEL %r, using INFO", level)
