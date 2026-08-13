"""HTTP surface: two streaming endpoints and a health check.

Thin by design. A route validates its input, calls one agent function, and frames
whatever that yields as server-sent events. All the judgement lives in `agent`,
all the vocabulary in `schemas`, the wire format in `a2ui`, and all the markup in
the frontend's A2UI catalog.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

import a2ui
import agent
import catalog
import documents
from schemas import Turn

# The app entrypoint is the one place a dotenv load belongs; importing this for
# its side effect anywhere else would make module import order load-bearing.
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)

logger = logging.getLogger("signal.api")

app = FastAPI(
    title="Signal · Generative UI POC",
    summary="Agent output as design-system molecules, streamed.",
    version="0.1.0",
)

# nginx proxies /api in the container build, so the browser only ever makes
# same-origin requests. This is for the dev server on :5173 and for curl.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class InspectRequest(BaseModel):
    """A review-pane question about one inspected molecule."""

    model_config = ConfigDict(extra="forbid")

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


# Buffering is the one thing that silently breaks this demo: hold the frames and
# the progressive render becomes a single late repaint, which is precisely the
# behaviour the POC exists to disprove. nginx gets told via X-Accel-Buffering.
STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@app.get("/api/health", summary="Liveness probe.")
def health() -> dict[str, object]:
    """Report liveness, the model, and the UI protocol this build speaks.

    The protocol and catalog are here because they are the two things a client
    has to agree with the server about. A browser holding a stale catalog is
    otherwise indistinguishable from an agent producing nothing.
    """
    return {
        "ok": True,
        "model": agent.MODEL,
        "has_api_key": bool(os.getenv("OPENAI_API_KEY")),
        "protocol": a2ui.VERSION,
        "catalog_id": a2ui.CATALOG_ID,
    }


@app.get("/api/documents", summary="The documents this build can analyse.")
def list_documents() -> dict[str, object]:
    """List the available documents, for the picker.

    `expect` is included deliberately: it is the one-line prediction of what shape
    each document should produce, so a demo can state the claim before running it
    rather than describing whatever came back.
    """
    return {
        "default": documents.DEFAULT_KEY,
        "documents": [
            {
                "key": document.key,
                "title": document.title,
                "client": document.client,
                "sector": document.sector,
                "reference": document.reference,
                "expect": document.expect,
            }
            for document in documents.DOCUMENTS.values()
        ],
    }


@app.get("/api/catalog", summary="The molecule vocabulary the agent generates against.")
def molecule_catalog() -> dict[str, object]:
    """The closed set of components the model may choose from, plus specimens.

    Derived from `schemas.py` by introspection rather than written out, so the
    field tables are the same constraints the structured-outputs call enforces.
    The specimens are compiled by `a2ui.py`, so what the page draws is the real
    component and not an illustration of one.
    """
    return catalog.describe()


@app.get("/api/rfp", summary="The header facts for one document.")
def rfp_header(document: str | None = None) -> dict[str, str]:
    """Return the static header for the document under review.

    The page chrome is not generated -- the title, client and reference come from
    the record, not from the model. Keeping this on a separate endpoint makes that
    boundary visible rather than implied.
    """
    record = documents.get(document)
    return {
        "title": record.title,
        "client": record.client,
        "sector": record.sector,
        "reference": record.reference,
    }


@app.get("/api/sections/rfp-overview", summary="Stream the analysis of one document.")
def stream_overview(document: str | None = None) -> StreamingResponse:
    """Stream the agent's molecules for one document, as they are decided."""
    return StreamingResponse(
        _sse(agent.run_overview(documents.get(document))),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@app.post("/api/inspect", summary="Ask about one inspected molecule.")
def inspect(request: InspectRequest) -> StreamingResponse:
    """Answer a review-pane question, scoped to the clicked datapoint."""
    return StreamingResponse(
        _sse(
            agent.run_inspect(
                documents.get(request.document),
                request.question,
                request.subject,
                request.history,
            )
        ),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
