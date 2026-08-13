"""HTTP surface: two streaming endpoints, a health check, and three reads.

Thin by design. A route validates its input, calls one service function, and
frames whatever that yields as server-sent events. All the judgement lives in
`app.services.agent`, all the vocabulary in `app.schemas`, the wire format in
`app.a2ui`, and all the markup in the frontend's A2UI catalog.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app import a2ui, documents
from app.api.schemas import (
    DocumentsResponse,
    DocumentSummary,
    HealthResponse,
    InspectRequest,
    RfpHeader,
)
from app.core.config import Settings, get_settings
from app.services import agent, catalog

router = APIRouter(prefix="/api")

SettingsDep = Annotated[Settings, Depends(get_settings)]

DocumentKey = Annotated[
    str | None,
    Query(max_length=64, description="Document key; falls back to the default when unknown."),
]

# Buffering is the one thing that silently breaks this demo: hold the frames and
# the progressive render becomes a single late repaint, which is precisely the
# behaviour the POC exists to disprove. nginx gets told via X-Accel-Buffering.
STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _sse(events: Iterator[agent.Event]) -> Iterator[str]:
    """Frame agent events as server-sent events.

    The event name is the agent's `kind`, so the client dispatches on the SSE
    event type rather than sniffing the payload. A trailing `done` event closes
    the stream explicitly -- the client should not have to treat a socket close
    as a successful completion, because it is also what a crash looks like.
    """
    for event in events:
        yield f"event: {event.kind}\ndata: {json.dumps(event.payload)}\n\n"
    yield "event: done\ndata: {}\n\n"


@router.get("/health", summary="Liveness probe.", response_model=HealthResponse)
def health(settings: SettingsDep) -> HealthResponse:
    """Report liveness, the model, and the UI protocol this build speaks.

    The protocol and catalog are here because they are the two things a client
    has to agree with the server about. A browser holding a stale catalog is
    otherwise indistinguishable from an agent producing nothing.
    """
    return HealthResponse(
        ok=True,
        model=settings.openai_model,
        has_api_key=settings.has_api_key,
        protocol=a2ui.VERSION,
        catalog_id=a2ui.CATALOG_ID,
    )


@router.get(
    "/documents",
    summary="The documents this build can analyse.",
    response_model=DocumentsResponse,
)
def list_documents() -> DocumentsResponse:
    """List the available documents, for the picker.

    `expect` is included deliberately: it is the one-line prediction of what shape
    each document should produce, so a demo can state the claim before running it
    rather than describing whatever came back.
    """
    return DocumentsResponse(
        default=documents.DEFAULT_KEY,
        documents=[
            DocumentSummary(
                key=document.key,
                title=document.title,
                client=document.client,
                sector=document.sector,
                reference=document.reference,
                expect=document.expect,
            )
            for document in documents.DOCUMENTS.values()
        ],
    )


@router.get("/catalog", summary="The molecule vocabulary the agent generates against.")
def molecule_catalog() -> dict[str, object]:
    """The closed set of components the model may choose from, plus specimens.

    Derived from `app.schemas` by introspection rather than written out, so the
    field tables are the same constraints the structured-outputs call enforces.
    The specimens are compiled by `app.a2ui`, so what the page draws is the real
    component and not an illustration of one.

    Not given a response model: the payload is a description of a schema, whose
    own shape is derived by introspection. Declaring a model for it would mean
    maintaining a second description of the first one.
    """
    return catalog.describe()


@router.get("/rfp", summary="The header facts for one document.", response_model=RfpHeader)
def rfp_header(document: DocumentKey = None) -> RfpHeader:
    """Return the static header for the document under review.

    The page chrome is not generated -- the title, client and reference come from
    the record, not from the model. Keeping this on a separate endpoint makes that
    boundary visible rather than implied.
    """
    record = documents.get(document)
    return RfpHeader(
        title=record.title,
        client=record.client,
        sector=record.sector,
        reference=record.reference,
    )


@router.get("/sections/rfp-overview", summary="Stream the analysis of one document.")
def stream_overview(settings: SettingsDep, document: DocumentKey = None) -> StreamingResponse:
    """Stream the agent's molecules for one document, as they are decided."""
    return StreamingResponse(
        _sse(agent.run_overview(documents.get(document), settings)),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@router.post("/inspect", summary="Ask about one inspected molecule.")
def inspect(request: InspectRequest, settings: SettingsDep) -> StreamingResponse:
    """Answer a review-pane question, scoped to the clicked datapoint."""
    return StreamingResponse(
        _sse(
            agent.run_inspect(
                documents.get(request.document),
                settings,
                question=request.question,
                subject=request.subject,
                history=request.history,
            )
        ),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
