"""The compiler's contract with the browser.

These are the assertions that would catch a protocol regression the frontend
cannot recover from: a component whose props are inline values instead of
bindings, a data model sent after the components that bind against it, or a
binding path that does not match the molecule's index.
"""

from __future__ import annotations

import pytest

from app import a2ui
from app.schemas import Callout, MetricGrid, Molecule, ScoreTable


def test_create_surface_carries_only_ids() -> None:
    message = a2ui.create_surface("s1")

    assert message == {
        "version": a2ui.VERSION,
        "createSurface": {"surfaceId": "s1", "catalogId": a2ui.CATALOG_ID},
    }


def test_component_for_binds_every_prop_rather_than_inlining_values(callout: Callout) -> None:
    component = a2ui.component_for(callout, 2)

    assert component["id"] == "m2"
    assert component["component"] == "Callout"
    props = {key: value for key, value in component.items() if key not in ("id", "component")}
    assert props, "a component with no props would render an empty band"
    for field, binding in props.items():
        assert binding == {"path": f"/molecules/2/{field}"}


def test_component_for_binds_the_shared_capabilities_on_every_family(
    molecules: list[Molecule],
) -> None:
    for index, molecule in enumerate(molecules):
        component = a2ui.component_for(molecule, index)
        for capability in a2ui.CAPABILITY_FIELDS:
            assert component[capability] == {"path": f"/molecules/{index}/{capability}"}


def test_component_name_raises_for_an_unmapped_family() -> None:
    with pytest.raises(KeyError):
        a2ui.component_name("case_card")


def test_open_surface_seeds_an_empty_model_so_no_binding_resolves_against_nothing() -> None:
    create, seed = a2ui.open_surface("s1")

    assert "createSurface" in create
    assert seed["updateDataModel"] == {"surfaceId": "s1", "path": "/", "value": {"molecules": []}}


def test_append_molecule_sends_data_before_components(molecules: list[Molecule]) -> None:
    data, components = a2ui.append_molecule("s1", molecules)

    assert "updateDataModel" in data
    assert "updateComponents" in components
    sent = data["updateDataModel"]["value"]["molecules"]
    assert len(sent) == len(molecules), "the whole model is written at /, not just the new index"


def test_append_molecule_sends_only_the_newest_component_and_the_root(
    molecules: list[Molecule],
) -> None:
    _, components = a2ui.append_molecule("s1", molecules)

    ids = [component["id"] for component in components["updateComponents"]["components"]]
    assert ids == [f"m{len(molecules) - 1}", a2ui.ROOT_ID], (
        "resending settled components would repaint bands already on screen"
    )


def test_replace_surface_sends_the_whole_tree(molecules: list[Molecule]) -> None:
    data, components = a2ui.replace_surface("s1", molecules)

    ids = [component["id"] for component in components["updateComponents"]["components"]]
    assert ids == ["m0", "m1", "m2", a2ui.ROOT_ID]
    assert len(data["updateDataModel"]["value"]["molecules"]) == 3


def test_root_children_are_in_render_order(molecules: list[Molecule]) -> None:
    root = a2ui.root_component(len(molecules))

    assert root["children"] == ["m0", "m1", "m2"]


def test_full_surface_creates_then_fills(molecules: list[Molecule]) -> None:
    messages = a2ui.full_surface("s1", molecules)

    assert "createSurface" in messages[0]
    assert len(messages) == 3


def test_data_model_keeps_the_type_for_debuggability(callout: Callout) -> None:
    model = a2ui.data_model([callout])

    assert model["molecules"][0]["type"] == "callout"


def test_directness_cost_counts_what_the_compiler_wrote(molecules: list[Molecule]) -> None:
    cost = a2ui.directness_cost(molecules)

    # One component per molecule plus the root.
    assert cost["components"] == len(molecules) + 1
    assert cost["direct_bytes"] > cost["typed_bytes"], (
        "the component tree is exactly the difference between the two"
    )
    assert cost["bindings"] > 0


def test_directness_cost_of_an_empty_section_still_reports_the_root() -> None:
    cost = a2ui.directness_cost([])

    assert cost["components"] == 1
    assert cost["bindings"] == 0


@pytest.mark.parametrize(
    ("family", "expected"),
    [
        ("metric_grid", "MetricGrid"),
        ("callout", "Callout"),
        ("score_table", "ScoreTable"),
        ("phase_plan", "PhasePlan"),
        ("arc_beats", "ArcBeats"),
    ],
)
def test_every_family_in_the_union_has_a_view(family: str, expected: str) -> None:
    assert a2ui.component_name(family) == expected


def test_the_view_table_covers_the_whole_molecule_union(
    metric_grid: MetricGrid, callout: Callout, score_table: ScoreTable
) -> None:
    """A family added to `schemas.Molecule` without a `_VIEW` row cannot be drawn."""
    from typing import get_args

    for member in get_args(Molecule):
        family = member.model_fields["type"].default
        assert a2ui.component_name(family), f"{family} has no view"
