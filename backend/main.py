"""HTTP surface: two streaming endpoints and a health check.

Thin by design. A route validates its input, calls one agent function, and frames
whatever that yields as server-sent events. All the judgement lives in `agent`,
all the vocabulary in `schemas`, and all the markup in the frontend registry.
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

import agent
import rfp_document
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
    """Report liveness and whether a model key is configured."""
    return {"ok": True, "model": agent.MODEL, "has_api_key": bool(os.getenv("OPENAI_API_KEY"))}


@app.get("/api/rfp", summary="The RFP header facts.")
def rfp_header() -> dict[str, str]:
    """Return the static header for the RFP under review.

    The page chrome is not generated -- the title, client and reference come from
    the record, not from the model. Keeping this on a separate endpoint makes that
    boundary visible rather than implied.
    """
    return {
        "title": rfp_document.RFP_TITLE,
        "client": rfp_document.RFP_CLIENT,
        "sector": rfp_document.RFP_SECTOR,
        "reference": rfp_document.RFP_REFERENCE,
    }


@app.get("/api/sections/rfp-overview", summary="Stream the RFP Overview section.")
def stream_overview() -> StreamingResponse:
    """Stream the RFP Overview agent's molecules as they are decided."""
    return StreamingResponse(
        _sse(agent.run_overview()),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@app.post("/api/inspect", summary="Ask about one inspected molecule.")
def inspect(request: InspectRequest) -> StreamingResponse:
    """Answer a review-pane question, scoped to the clicked datapoint."""
    return StreamingResponse(
        _sse(agent.run_inspect(request.question, request.subject, request.history)),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )
