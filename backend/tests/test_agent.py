"""The agent's non-model logic: the sanitiser, the clock, and the fallbacks.

Everything here runs without a model. `_stream_section` is the only function that
talks to OpenAI, and it is excluded on purpose -- a test that mocked the SDK's
streaming event sequence would assert the shape of the mock.
"""

from __future__ import annotations

import pytest

from app import documents
from app.core.config import Settings
from app.errors import MoleculeUnusableError
from app.schemas import Callout, ErrorCode, MetricGrid, ScoreTable
from app.services import agent


class TestSanitize:
    def test_keeps_a_complete_callout_untouched(self, callout: Callout) -> None:
        assert agent._sanitize(callout) == callout

    def test_drops_an_orphan_source_when_there_is_no_label(self) -> None:
        molecule = Callout(tone="context", lead="Stated.", body="b", source="§4")

        repaired = agent._sanitize(molecule)

        assert isinstance(repaired, Callout)
        assert repaired.source == "", "a source with no label renders as an orphan line"
        assert repaired.body == "b", "the repair must not touch anything else"

    def test_keeps_a_source_that_has_its_label(self) -> None:
        molecule = Callout(tone="context", body="b", label="Budget", source="§4")

        repaired = agent._sanitize(molecule)

        assert isinstance(repaired, Callout)
        assert repaired.source == "§4"

    def test_raises_on_a_callout_with_neither_lead_nor_label(self) -> None:
        molecule = Callout(tone="risk", body="a bare paragraph in a banded surface")

        with pytest.raises(MoleculeUnusableError, match="neither lead nor label"):
            agent._sanitize(molecule)

    def test_raises_on_a_total_with_no_rows(self, score_table: ScoreTable) -> None:
        # `rows` has min_length=1, so the empty state has to be constructed past
        # validation -- which is exactly the state the sanitiser exists to catch.
        molecule = ScoreTable.model_construct(
            type="score_table", rows=[], total=score_table.total, inspect=False, signal=False
        )

        with pytest.raises(MoleculeUnusableError, match="total but no rows"):
            agent._sanitize(molecule)

    def test_leaves_other_families_alone(self, metric_grid: MetricGrid) -> None:
        assert agent._sanitize(metric_grid) == metric_grid


class TestParsePartial:
    def test_returns_none_for_a_snapshot_that_is_not_a_dict(self) -> None:
        assert agent._parse_partial("half a str") is None
        assert agent._parse_partial(None) is None
        assert agent._parse_partial([]) is None

    def test_returns_none_before_the_type_discriminator_arrives(self) -> None:
        assert agent._parse_partial({"body": "part"}) is None

    def test_returns_none_for_a_half_written_molecule(self) -> None:
        assert agent._parse_partial({"type": "callout"}) is None, "no body yet"

    def test_returns_none_for_a_structurally_valid_but_undrawable_molecule(self) -> None:
        assert agent._parse_partial({"type": "callout", "tone": "risk", "body": "b"}) is None

    def test_returns_the_sanitised_molecule_once_it_is_whole(self) -> None:
        parsed = agent._parse_partial(
            {"type": "callout", "tone": "risk", "lead": "Gap.", "body": "b", "source": "§4"}
        )

        assert isinstance(parsed, Callout)
        assert parsed.source == "", "the optimistic path sanitises too"

    def test_rejects_a_hallucinated_field(self) -> None:
        raw = {"type": "callout", "tone": "risk", "lead": "Gap.", "body": "b", "colour": "#f00"}

        assert agent._parse_partial(raw) is None, "extra='forbid' has to hold on this path"


class TestUsable:
    def test_drops_the_undrawable_and_keeps_the_rest(self, callout: Callout) -> None:
        broken = Callout(tone="risk", body="no lead, no label")

        pairs = agent._usable([callout, broken, callout])

        assert len(pairs) == 2, "one bad molecule costs that molecule, not the section"

    def test_returns_the_returned_and_drawn_pair(self) -> None:
        molecule = Callout(tone="context", lead="Stated.", body="b", source="§4")

        [(returned, drawn)] = agent._usable([molecule])

        assert isinstance(returned, Callout)
        assert returned.source == "§4", "the model's own output, for the walkthrough"
        assert isinstance(drawn, Callout)
        assert drawn.source == "", "and what actually renders"

    def test_truncates_to_the_molecule_budget(self, callout: Callout) -> None:
        from app.schemas import MAX_MOLECULES

        pairs = agent._usable([callout] * (MAX_MOLECULES + 3))

        assert len(pairs) == MAX_MOLECULES

    def test_an_empty_plan_yields_no_pairs(self) -> None:
        assert agent._usable([]) == []


class TestCounts:
    def test_counts_molecules_and_signals(self, callout: Callout, metric_grid: MetricGrid) -> None:
        signalled = callout.model_copy(update={"signal": True})

        counts = agent._counts([callout, signalled, metric_grid])

        assert counts == {"molecule_count": 3, "signal_count": 1}

    def test_an_empty_section_counts_zero(self) -> None:
        assert agent._counts([]) == {"molecule_count": 0, "signal_count": 0}


class TestClock:
    def test_first_molecule_is_unset_until_a_molecule_is_marked(self) -> None:
        clock = agent.Clock()

        assert clock.first_molecule_ms is None
        assert clock.elapsed_ms() >= 0
        assert clock.first_molecule_ms is None, "reading the clock must not record a first paint"

    def test_marking_records_the_first_time_only(self) -> None:
        clock = agent.Clock()

        first = clock.mark_molecule()
        clock.mark_molecule()

        assert clock.first_molecule_ms == first


class TestTokens:
    def test_reports_none_when_the_api_did_not(self) -> None:
        class NoUsage:
            usage = None

        assert agent._tokens(NoUsage()) is None, "unknown cost is not zero cost"

    def test_reports_the_three_figures_the_readout_shows(self) -> None:
        class Usage:
            prompt_tokens = 1200
            completion_tokens = 300
            total_tokens = 1500

        class Completion:
            usage = Usage()

        assert agent._tokens(Completion()) == {"prompt": 1200, "completion": 300, "total": 1500}


class TestFallback:
    @pytest.mark.parametrize(
        "code", ["missing_api_key", "schema_validation_failed", "upstream_error"]
    )
    def test_every_error_code_has_copy_and_renders_as_a_molecule(self, code: ErrorCode) -> None:
        events = list(agent._fallback(code, agent.Clock()))

        kinds = [event.kind for event in events]
        assert kinds == ["a2ui", "a2ui", "meta"]
        assert "updateComponents" in events[1].payload, "the failure is drawn by the renderer"

    def test_replaces_rather_than_creates_because_the_surface_already_exists(self) -> None:
        events = list(agent._fallback("upstream_error", agent.Clock()))

        assert not any("createSurface" in event.payload for event in events)

    def test_the_meta_event_reports_the_failure_without_internals(self) -> None:
        [meta] = [
            event
            for event in agent._fallback("upstream_error", agent.Clock())
            if event.kind == "meta"
        ]

        assert meta.payload["ok"] is False
        assert meta.payload["error"] == "upstream_error"
        assert meta.payload["molecule_count"] == 1

    def test_every_error_code_in_the_literal_has_copy(self) -> None:
        from typing import get_args

        assert set(get_args(ErrorCode)) == set(agent.FALLBACK_COPY)


class TestPrompts:
    def test_the_section_prompt_appends_the_document_to_a_shared_base(self) -> None:
        cedar = agent.section_prompt(documents.CEDAR)
        northwind = agent.section_prompt(documents.NORTHWIND)

        assert agent.SECTION_PROMPT_BASE in cedar
        assert agent.SECTION_PROMPT_BASE in northwind
        assert "Cedar Wellness" not in northwind, (
            "one document's peculiarities must not travel to another"
        )

    def test_the_inspect_prompt_carries_the_document(self) -> None:
        assert "Meridian" in agent.inspect_prompt(documents.MERIDIAN)


class TestRunOverviewWithoutAKey:
    """The keyless path is a real, reachable branch -- it is the first-run state."""

    def test_opens_a_surface_before_it_can_fail(self, no_key_settings: Settings) -> None:
        events = list(agent.run_overview(documents.CEDAR, no_key_settings))

        assert "createSurface" in events[0].payload

    def test_yields_a_drawable_fallback_and_never_raises(self, no_key_settings: Settings) -> None:
        events = list(agent.run_overview(documents.CEDAR, no_key_settings))

        meta = [event for event in events if event.kind == "meta"][-1]
        assert meta.payload["error"] == "missing_api_key"
        assert meta.payload["molecule_count"] == 1

    def test_says_nothing_about_the_key_itself(self, no_key_settings: Settings) -> None:
        events = list(agent.run_overview(documents.CEDAR, no_key_settings))

        body = str([event.payload for event in events])
        assert "test-key" not in body


class TestRunInspectWithoutAKey:
    def test_answers_with_the_missing_key_copy(self, no_key_settings: Settings) -> None:
        events = list(
            agent.run_inspect(
                documents.CEDAR,
                no_key_settings,
                question="Where did this come from?",
                subject="the budget tile",
                history=[],
            )
        )

        answer = [event for event in events if event.kind == "answer"][0]
        assert "OPENAI_API_KEY" in answer.payload["answer"]
        assert answer.payload["surface_id"] is None
