"""The HTTP surface, exercised through the app.

The streaming routes are read to completion here. That matters more than it looks:
a generator that raises partway through a `StreamingResponse` produces a
successful 200 followed by a truncated body, so a test that only asserted the
status code would pass on a broken stream.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import a2ui, documents
from app.api.middleware import REQUEST_ID_HEADER

pytestmark = pytest.mark.integration


def _events(body: str) -> list[tuple[str, dict[str, object]]]:
    """Parse an SSE body into `(event, data)` pairs."""
    parsed: list[tuple[str, dict[str, object]]] = []
    for frame in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        parsed.append((lines["event"], json.loads(lines["data"])))
    return parsed


class TestHealth:
    def test_reports_the_protocol_and_catalog_the_client_must_agree_with(
        self, client: TestClient
    ) -> None:
        payload = client.get("/api/health").json()

        assert payload == {
            "ok": True,
            "model": "test-model",
            "has_api_key": False,
            "protocol": a2ui.VERSION,
            "catalog_id": a2ui.CATALOG_ID,
        }

    def test_never_returns_the_key_itself(self, client: TestClient) -> None:
        assert "openai_api_key" not in client.get("/api/health").text


class TestDocuments:
    def test_lists_every_document_with_its_prediction(self, client: TestClient) -> None:
        payload = client.get("/api/documents").json()

        assert payload["default"] == documents.DEFAULT_KEY
        assert len(payload["documents"]) == len(documents.DOCUMENTS)
        assert all(entry["expect"] for entry in payload["documents"])

    def test_does_not_ship_the_document_bodies_to_the_picker(self, client: TestClient) -> None:
        [entry, *_] = client.get("/api/documents").json()["documents"]

        assert "body" not in entry


class TestRfpHeader:
    def test_returns_the_requested_document(self, client: TestClient) -> None:
        payload = client.get("/api/rfp", params={"document": "halcyon-bank"}).json()

        assert payload["client"] == "Halcyon Bank"

    def test_falls_back_to_the_default_rather_than_4xx(self, client: TestClient) -> None:
        response = client.get("/api/rfp", params={"document": "no-such-document"})

        assert response.status_code == 200
        assert response.json()["title"] == documents.CEDAR.title

    def test_defaults_when_the_parameter_is_absent(self, client: TestClient) -> None:
        assert client.get("/api/rfp").json()["client"] == documents.CEDAR.client

    def test_rejects_an_over_long_key(self, client: TestClient) -> None:
        response = client.get("/api/rfp", params={"document": "x" * 65})

        assert response.status_code == 422


class TestCatalog:
    def test_describes_every_family_with_its_specimens(self, client: TestClient) -> None:
        payload = client.get("/api/catalog").json()

        assert len(payload["families"]) == 5
        assert payload["a2ui"], "the gallery draws real components, not an illustration"

    def test_reports_the_bound_that_validation_actually_enforces(self, client: TestClient) -> None:
        from app.schemas import MAX_MOLECULES

        assert client.get("/api/catalog").json()["max_molecules"] == MAX_MOLECULES


class TestOverviewStream:
    def test_streams_a_drawable_fallback_when_no_key_is_configured(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/sections/rfp-overview")

        assert response.status_code == 200
        events = _events(response.text)
        assert events[0][0] == "a2ui"
        assert events[-1][0] == "done", "the client must not have to read a socket close as success"

    def test_sets_the_headers_that_stop_a_proxy_buffering_the_stream(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/sections/rfp-overview")

        assert response.headers["x-accel-buffering"] == "no"
        assert "no-transform" in response.headers["cache-control"]

    def test_the_meta_event_closes_the_stream_before_done(self, client: TestClient) -> None:
        events = _events(client.get("/api/sections/rfp-overview").text)

        kinds = [kind for kind, _ in events]
        assert kinds[-2:] == ["meta", "done"]


class TestInspect:
    def test_answers_a_well_formed_question(self, client: TestClient) -> None:
        response = client.post(
            "/api/inspect",
            json={"question": "Where is this from?", "subject": "the budget tile"},
        )

        assert response.status_code == 200
        assert [kind for kind, _ in _events(response.text)][-1] == "done"

    @pytest.mark.parametrize(
        "payload",
        [
            {"subject": "a tile"},
            {"question": "", "subject": "a tile"},
            {"question": "q", "subject": ""},
            {"question": "q", "subject": "a tile", "colour": "#f00"},
            {"question": "q" * 501, "subject": "a tile"},
            {"question": "q", "subject": "a tile", "history": [{"role": "system", "content": "x"}]},
        ],
    )
    def test_rejects_a_malformed_body(self, client: TestClient, payload: dict[str, object]) -> None:
        assert client.post("/api/inspect", json=payload).status_code == 422

    def test_caps_the_replayed_history(self, client: TestClient) -> None:
        history = [{"role": "user", "content": "q"}] * 13

        response = client.post(
            "/api/inspect", json={"question": "q", "subject": "s", "history": history}
        )

        assert response.status_code == 422


class TestRequestId:
    def test_mints_one_and_echoes_it(self, client: TestClient) -> None:
        response = client.get("/api/health")

        assert response.headers[REQUEST_ID_HEADER]

    def test_honours_an_inbound_id_so_a_proxy_trace_carries_through(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/health", headers={REQUEST_ID_HEADER: "abc123"})

        assert response.headers[REQUEST_ID_HEADER] == "abc123"

    def test_replaces_an_id_that_could_forge_a_log_line(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={REQUEST_ID_HEADER: "a\nWARNING fake"})

        assert "\n" not in response.headers[REQUEST_ID_HEADER]


class TestCors:
    def test_allows_the_configured_origin(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})

        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_does_not_allow_an_unconfigured_origin(self, client: TestClient) -> None:
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})

        assert "access-control-allow-origin" not in response.headers
