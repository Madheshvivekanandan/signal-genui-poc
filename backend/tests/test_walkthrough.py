"""The walkthrough trace: which molecule is followed, and what each stage shows."""

from __future__ import annotations

from app import a2ui
from app.schemas import Callout, MetricGrid, Molecule, PhasePlan
from app.services import walkthrough


class TestChoose:
    def test_prefers_a_callout_because_it_shows_the_most_machinery(
        self, metric_grid: MetricGrid, callout: Callout
    ) -> None:
        assert walkthrough.choose([metric_grid, callout]) == 1

    def test_falls_back_through_the_preference_order(
        self, metric_grid: MetricGrid, phase_plan: PhasePlan
    ) -> None:
        assert walkthrough.choose([metric_grid, phase_plan]) == 1

    def test_traces_the_first_molecule_when_no_preferred_family_is_present(self) -> None:
        assert walkthrough.choose([]) == 0


class TestRepairs:
    def test_reports_nothing_when_the_model_needed_no_repair(self, callout: Callout) -> None:
        values = callout.model_dump(mode="json")

        assert walkthrough.repairs(values, values) == []

    def test_reports_the_field_the_sanitiser_changed(self) -> None:
        before = {"source": "§4", "body": "b"}
        after = {"source": "", "body": "b"}

        [change] = walkthrough.repairs(before, after)

        assert change == {"field": "source", "was": '"§4"', "now": '""'}


class TestResolved:
    def test_pairs_every_binding_with_the_value_the_binder_finds(self, callout: Callout) -> None:
        component = a2ui.component_for(callout, 0)
        values = callout.model_dump(mode="json")

        rows = walkthrough.resolved(component, values)

        assert {row["field"] for row in rows} == set(values) - {"type"}
        [body] = [row for row in rows if row["field"] == "body"]
        assert body["value"] == callout.body
        assert body["path"] == "/molecules/0/body"

    def test_skips_the_components_own_identity(self, callout: Callout) -> None:
        component = a2ui.component_for(callout, 0)

        fields = {row["field"] for row in walkthrough.resolved(component, {})}

        assert "id" not in fields and "component" not in fields

    def test_shows_a_collection_as_json_since_it_cannot_be_shown_as_a_scalar(
        self, metric_grid: MetricGrid
    ) -> None:
        component = a2ui.component_for(metric_grid, 0)
        values = metric_grid.model_dump(mode="json")

        [metrics] = [
            row for row in walkthrough.resolved(component, values) if row["field"] == "metrics"
        ]

        assert metrics["value"] is None
        assert metrics["json"] is not None


class TestBuild:
    def _build(self, molecules: list[Molecule], index: int) -> dict[str, object]:
        return walkthrough.build(
            instructions="INSTRUCTIONS",
            document_text="DOCUMENT",
            model="test-model",
            returned=molecules[index],
            drawn=molecules[index],
            molecules=molecules,
            index=index,
            returned_count=len(molecules) + 1,
            drawn_count=len(molecules),
        )

    def test_keeps_the_prompt_halves_separate(self, molecules: list[Molecule]) -> None:
        trace = self._build(molecules, 1)

        assert trace["instructions"] == "INSTRUCTIONS"
        assert trace["document_text"] == "DOCUMENT"

    def test_reports_a_drop_the_traced_molecule_cannot_show(
        self, molecules: list[Molecule]
    ) -> None:
        trace = self._build(molecules, 1)

        assert trace["dropped_count"] == 1, (
            "the traced molecule is a survivor, so the run's totals have to carry this"
        )

    def test_the_data_stage_shows_the_real_section_message_not_a_slice(
        self, molecules: list[Molecule]
    ) -> None:
        trace = self._build(molecules, 1)

        message = trace["data_message"]
        assert isinstance(message, dict)
        update = message["updateDataModel"]
        assert update["surfaceId"] == a2ui.SECTION_SURFACE_ID
        assert len(update["value"]["molecules"]) == len(molecules)
        assert trace["data_path"] == "/molecules/1"

    def test_the_final_surface_keeps_the_binding_paths_the_stage_above_explained(
        self, molecules: list[Molecule]
    ) -> None:
        trace = self._build(molecules, 2)

        messages = trace["a2ui"]
        assert isinstance(messages, list)
        _, data, components = messages
        assert data["updateDataModel"]["value"]["molecules"][:2] == [None, None], (
            "padded rather than re-indexed, so /molecules/2/... still resolves"
        )
        [component, root] = components["updateComponents"]["components"]
        assert component["id"] == "m2"
        assert root["children"] == ["m2"]

    def test_names_the_component_that_draws_the_traced_family(
        self, molecules: list[Molecule]
    ) -> None:
        trace = self._build(molecules, 1)

        assert trace["family"] == "callout"
        assert trace["component_name"] == "Callout"
