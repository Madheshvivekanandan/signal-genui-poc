"""The streamed success path: what a client actually receives on a good run.

These are the assertions that hold the POC's two central claims. First, that the
interface arrives progressively -- a molecule is compiled and pushed while the
model is still writing the next one. Second, that the optimistic pass is
corrected: whatever it guessed from half-written JSON is overwritten by the
validated object before the user can click it.

The model is faked (see `fakes.py`); everything below it is the real code.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app import a2ui, documents
from app.core.config import Settings
from app.errors import ModelRefusedError
from app.schemas import Callout, InspectAnswer, Molecule, Turn
from app.services import agent
from tests import fakes

# Captured at import, before the autouse fixture below replaces it, so the one
# test that exercises client construction can reach the real function.
_REAL_GET_CLIENT = agent.get_client


@pytest.fixture(autouse=True)
def _no_real_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly rather than reaching the network if a test forgets to fake."""

    def _forbidden(settings: Settings) -> None:
        raise AssertionError("a test tried to build a real OpenAI client")

    monkeypatch.setattr(agent, "get_client", _forbidden)


def _run(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    client: fakes.FakeClient,
    document: documents.Document | None = None,
) -> list[agent.Event]:
    monkeypatch.setattr(agent, "get_client", lambda _settings: client)
    return list(agent.run_overview(document or documents.CEDAR, settings))


class TestOptimisticPass:
    def test_pushes_each_settled_molecule_before_the_stream_closes(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        # The `plan` event marks the end of the stream, so anything before it was
        # emitted while the model was still writing.
        plan_at = [event.kind for event in events].index("plan")
        before = [event for event in events[:plan_at] if event.kind == "a2ui"]
        assert any("updateComponents" in event.payload for event in before), (
            "nothing was drawn until the generation finished -- the progressive render is gone"
        )

    def test_holds_back_the_last_molecule_because_nothing_proves_it_finished(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        plan_at = [event.kind for event in events].index("plan")
        counts = [event.payload for event in events[:plan_at] if event.kind == "meta"]
        assert counts[-1]["molecule_count"] == len(molecules) - 1

    def test_reports_a_time_to_first_molecule(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        meta = events[-1].payload
        assert meta["first_molecule_ms"] is not None
        assert meta["first_molecule_ms"] <= meta["total_ms"]

    def test_reports_no_first_molecule_when_nothing_settled_optimistically(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, callout: Callout
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for([callout]))

        assert events[-1].payload["first_molecule_ms"] is None, (
            "a single-molecule run has nothing to prove finished; its fallback is not a fast paint"
        )


class TestAuthoritativePass:
    def test_replaces_the_whole_surface_after_the_stream(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        plan_at = [event.kind for event in events].index("plan")
        after = [event.payload for event in events[plan_at:] if event.kind == "a2ui"]
        trees = [
            message["updateComponents"]["components"]
            for message in after
            if "updateComponents" in message
            and message["updateComponents"]["surfaceId"] == a2ui.SECTION_SURFACE_ID
        ]
        assert [component["id"] for component in trees[0]] == ["m0", "m1", "m2", a2ui.ROOT_ID]

    def test_the_closing_meta_counts_the_drawn_section(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        meta = events[-1].payload
        assert meta["ok"] is True
        assert meta["error"] is None
        assert meta["molecule_count"] == len(molecules)
        assert meta["model"] == "test-model"

    def test_reports_the_token_usage_it_asked_the_api_for(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        assert events[-1].payload["tokens"] == {"prompt": 1200, "completion": 300, "total": 1500}

    def test_asks_for_usage_because_a_streamed_response_omits_it_otherwise(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        client = fakes.client_for(molecules)
        _run(monkeypatch, keyed_settings, client)

        [call] = client.completions.calls
        assert call["stream_options"] == {"include_usage": True}
        assert call["model"] == "test-model"

    def test_reports_unknown_cost_as_none_rather_than_zero(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules, usage=None))

        assert events[-1].payload["tokens"] is None

    def test_reports_what_the_compiler_wrote_on_the_models_behalf(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        directness = events[-1].payload["directness"]
        assert directness["components"] == len(molecules) + 1


class TestPlanEvent:
    def test_sends_the_models_own_output_before_the_sanitiser_touches_it(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        orphan = Callout(tone="context", lead="Stated.", body="b", source="§4")

        events = _run(monkeypatch, keyed_settings, fakes.client_for([orphan, orphan]))

        [plan] = [event.payload for event in events if event.kind == "plan"]
        assert plan["molecules"][0]["source"] == "§4", (
            "comparing returned against drawn is how a repair becomes visible"
        )

    def test_nothing_renders_from_the_plan_channel(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        [plan] = [event.payload for event in events if event.kind == "plan"]
        assert "createSurface" not in plan and "updateComponents" not in plan


class TestTraceEvent:
    def test_traces_one_molecule_on_its_own_surface(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        [trace] = [event.payload for event in events if event.kind == "trace"]
        assert trace["family"] == "callout"
        assert "a2ui" not in trace, "the frames are moved onto the a2ui channel, not duplicated"

    def test_the_traced_surface_frames_are_sent_on_the_a2ui_channel(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        from app.services import walkthrough

        events = _run(monkeypatch, keyed_settings, fakes.client_for(molecules))

        surfaces = {
            message["createSurface"]["surfaceId"]
            for message in (event.payload for event in events if event.kind == "a2ui")
            if "createSurface" in message
        }
        assert surfaces == {a2ui.SECTION_SURFACE_ID, walkthrough.SURFACE_ID}

    def test_reports_the_run_totals_so_a_drop_is_visible(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, callout: Callout
    ) -> None:
        broken = Callout(tone="risk", body="no lead, no label")

        events = _run(monkeypatch, keyed_settings, fakes.client_for([callout, broken, callout]))

        [trace] = [event.payload for event in events if event.kind == "trace"]
        assert trace["returned_count"] == 3
        assert trace["drawn_count"] == 2
        assert trace["dropped_count"] == 1


class TestFailurePaths:
    def test_a_refusal_becomes_a_drawable_fallback(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        client = fakes.client_for(molecules, refusal="I cannot help with that.")

        events = _run(monkeypatch, keyed_settings, client)

        assert events[-1].payload["error"] == "upstream_error"

    def test_a_refusal_reason_never_reaches_the_client(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        client = fakes.client_for(molecules, refusal="internal policy detail")

        events = _run(monkeypatch, keyed_settings, client)

        assert "internal policy detail" not in str([event.payload for event in events])

    def test_a_refusal_raises_the_typed_error_at_the_seam(self) -> None:
        with pytest.raises(ModelRefusedError) as caught:
            raise ModelRefusedError("because")

        assert caught.value.reason == "because"
        assert "because" not in str(caught.value), "the reason is for the log, not the message"

    def test_an_empty_completion_becomes_a_drawable_fallback(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        client = fakes.FakeClient(
            fakes.FakeCompletions(
                deltas=[],
                completion=fakes.Completion([fakes.Choice(fakes.Message(parsed=None))]),
            )
        )

        events = _run(monkeypatch, keyed_settings, client)

        assert events[-1].payload["error"] == "upstream_error"

    def test_an_upstream_exception_becomes_a_drawable_fallback(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        def _raise(_settings: Settings) -> None:
            raise ConnectionError("no route to host")

        monkeypatch.setattr(agent, "get_client", _raise)

        events = list(agent.run_overview(documents.CEDAR, keyed_settings))

        assert events[-1].payload["error"] == "upstream_error"
        assert "no route to host" not in str([event.payload for event in events])

    def test_a_validation_error_is_reported_as_such(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, molecules: list[Molecule]
    ) -> None:
        client = fakes.client_for(molecules)

        def _raise(**_kwargs: object) -> None:
            raise ValidationError.from_exception_data("SectionPlan", [])

        monkeypatch.setattr(client.completions, "stream", _raise)

        events = _run(monkeypatch, keyed_settings, client)

        assert events[-1].payload["error"] == "schema_validation_failed"

    def test_a_plan_of_nothing_drawable_falls_back(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        broken = Callout(tone="risk", body="no lead, no label")

        events = _run(monkeypatch, keyed_settings, fakes.client_for([broken]))

        assert events[-1].payload["error"] == "unusable_molecules"


class TestRunInspect:
    def _client(self, answer: InspectAnswer) -> fakes.FakeClient:
        return fakes.FakeClient(
            fakes.FakeCompletions(
                parse_result=fakes.Completion([fakes.Choice(fakes.Message(parsed=answer))])
            )
        )

    def _run_inspect(
        self,
        monkeypatch: pytest.MonkeyPatch,
        settings: Settings,
        client: fakes.FakeClient,
        history: list[Turn] | None = None,
    ) -> list[agent.Event]:
        monkeypatch.setattr(agent, "get_client", lambda _settings: client)
        return list(
            agent.run_inspect(
                documents.CEDAR,
                settings,
                question="Where did this come from?",
                subject="the budget tile",
                history=history or [],
            )
        )

    def test_answers_with_prose_and_no_surface_when_nothing_is_attached(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        client = self._client(InspectAnswer(answer="§4 states no envelope."))

        events = self._run_inspect(monkeypatch, keyed_settings, client)

        [answer] = [event.payload for event in events if event.kind == "answer"]
        assert answer == {"answer": "§4 states no envelope.", "surface_id": None}

    def test_sends_an_attached_surface_before_the_answer_that_references_it(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, callout: Callout
    ) -> None:
        client = self._client(InspectAnswer(answer="Here is the source.", molecules=[callout]))

        events = self._run_inspect(monkeypatch, keyed_settings, client)

        kinds = [event.kind for event in events]
        assert kinds.index("a2ui") < kinds.index("answer"), (
            "the pane would render a turn pointing at a surface the processor has not seen"
        )
        [answer] = [event.payload for event in events if event.kind == "answer"]
        assert str(answer["surface_id"]).startswith(a2ui.INSPECT_SURFACE_PREFIX)

    def test_gives_each_answer_its_own_surface(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings, callout: Callout
    ) -> None:
        client = self._client(InspectAnswer(answer="a", molecules=[callout]))

        first = self._run_inspect(monkeypatch, keyed_settings, client)
        second = self._run_inspect(monkeypatch, keyed_settings, client)

        def surface(events: list[agent.Event]) -> object:
            return [event.payload for event in events if event.kind == "answer"][0]["surface_id"]

        assert surface(first) != surface(second), (
            "a second question would overwrite the first one's intel card"
        )

    def test_drops_an_undrawable_attachment_rather_than_the_answer(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        broken = Callout(tone="risk", body="no lead, no label")
        client = self._client(InspectAnswer(answer="Still worth saying.", molecules=[broken]))

        events = self._run_inspect(monkeypatch, keyed_settings, client)

        [answer] = [event.payload for event in events if event.kind == "answer"]
        assert answer["answer"] == "Still worth saying."
        assert answer["surface_id"] is None

    def test_replays_the_conversation_between_the_prompt_and_the_question(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        client = self._client(InspectAnswer(answer="a"))
        history = [Turn(role="user", content="earlier"), Turn(role="assistant", content="reply")]

        self._run_inspect(monkeypatch, keyed_settings, client, history=list(history))

        [call] = client.completions.calls
        roles = [message["role"] for message in call["messages"]]
        assert roles == ["system", "system", "user", "assistant", "user"]
        assert call["messages"][-1]["content"] == "Where did this come from?"

    def test_an_upstream_failure_answers_with_the_generic_copy(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        client = fakes.FakeClient(
            fakes.FakeCompletions(parse_error=ConnectionError("no route to host"))
        )

        events = self._run_inspect(monkeypatch, keyed_settings, client)

        [answer] = [event.payload for event in events if event.kind == "answer"]
        assert "no route to host" not in answer["answer"]
        assert events[-1].payload["error"] == "upstream_error"

    def test_an_empty_completion_answers_with_the_generic_copy(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        client = fakes.FakeClient(
            fakes.FakeCompletions(
                parse_result=fakes.Completion([fakes.Choice(fakes.Message(parsed=None))])
            )
        )

        events = self._run_inspect(monkeypatch, keyed_settings, client)

        assert events[-1].payload["error"] == "upstream_error"


class TestGetClient:
    def test_builds_the_client_from_settings_and_reuses_it(
        self, monkeypatch: pytest.MonkeyPatch, keyed_settings: Settings
    ) -> None:
        built: list[str | None] = []

        class FakeOpenAI:
            def __init__(self, *, api_key: str | None = None) -> None:
                built.append(api_key)

        monkeypatch.setattr(agent, "get_client", _REAL_GET_CLIENT)
        monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)
        agent.reset_client()
        try:
            first = agent.get_client(keyed_settings)
            second = agent.get_client(keyed_settings)
        finally:
            agent.reset_client()

        assert first is second, "the connection pool is reused across requests"
        assert built == ["test-key-not-a-real-credential"]
