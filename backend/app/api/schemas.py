"""The wire shapes of the HTTP surface, separate from the agent's vocabulary.

`app.schemas` is what the *model* may return. This module is what a *client* may
send and will receive. Keeping them apart is not ceremony: the molecule union is
handed to the structured-outputs API as a response format, so widening it to suit
an HTTP response would change what the model is allowed to generate.

Every response model here is declared on its route, so the OpenAPI document
states the real shape rather than `object`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app import documents
from app.schemas import ErrorCode, Turn


class Strict(BaseModel):
    """Reject unknown fields on the way in, and declare them on the way out."""

    model_config = ConfigDict(extra="forbid")


class InspectRequest(Strict):
    """A review-pane question about one inspected molecule."""

    question: str = Field(min_length=1, max_length=500)
    subject: str = Field(
        min_length=1,
        max_length=300,
        description="Short description of the clicked molecule, so 'this' resolves.",
    )
    history: list[Turn] = Field(default_factory=list, max_length=12)
    document: str = Field(
        default=documents.DEFAULT_KEY,
        max_length=64,
        description="Which document the datapoint was drawn from.",
    )


class HealthResponse(Strict):
    """Liveness, the model, and the UI protocol this build speaks."""

    ok: bool
    model: str
    has_api_key: bool
    protocol: str
    catalog_id: str


class DocumentSummary(Strict):
    """One document as the picker needs it -- the header facts and the prediction."""

    key: str
    title: str
    client: str
    sector: str
    reference: str
    expect: str


class DocumentsResponse(Strict):
    """The documents this build can analyse, and which one opens by default."""

    default: str
    documents: list[DocumentSummary]


class RfpHeader(Strict):
    """The static header of the screen. Not generated -- read from the record."""

    title: str
    client: str
    sector: str
    reference: str


class ErrorResponse(Strict):
    """What a failed request returns.

    Deliberately two fields and no detail: an exception message can carry a
    partial API key, a file path or an upstream payload, and this body is rendered
    in a browser. Diagnostics go to the log under the request id.
    """

    error: ErrorCode | str = Field(description="A stable code, for the client to branch on.")
    detail: str = Field(description="One human-readable sentence. Never internals.")
