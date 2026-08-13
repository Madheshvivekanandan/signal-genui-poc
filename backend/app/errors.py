"""The exception hierarchy, rooted in one base. Stdlib only, no framework.

These replace the bare `ValueError`s the agent used to raise and catch. A bare
`ValueError` from `_sanitize` and a bare `ValueError` from a refusal were caught
by the same `except`, so the two were indistinguishable at the handler -- and any
unrelated `ValueError` raised inside the compiler would have been quietly
swallowed as though it were a refusal.

Nothing here knows an HTTP status code. `app.api.errors` owns that translation,
so the services stay free of the web layer.
"""

from __future__ import annotations


class AppError(Exception):
    """Base for every error this application raises deliberately."""


class MoleculeUnusableError(AppError):
    """A molecule is structurally valid but cannot be drawn.

    Raised by the sanitiser and caught per molecule: one unusable molecule costs
    that molecule, not the whole section.
    """


class AgentError(AppError):
    """The model did not produce usable output."""


class ModelRefusedError(AgentError):
    """The model declined to answer.

    Attributes:
        reason: The refusal text, for the log. Not shown to the client.
    """

    def __init__(self, reason: str) -> None:
        super().__init__("model refused the request")
        self.reason = reason


class EmptyCompletionError(AgentError):
    """The completion carried no parseable structured output."""

    def __init__(self) -> None:
        super().__init__("model returned no parseable output")
