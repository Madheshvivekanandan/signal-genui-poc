"""The vocabulary endpoint's introspection.

The claim this module makes is that the field tables cannot drift from what the
structured-outputs call enforces, because both are derived from `app.schemas`.
These tests hold that claim by asserting against the schema rather than against a
transcript of its current values.
"""

from __future__ import annotations

from typing import Any

from app import schemas
from app.services import catalog


def _family(described: dict[str, Any], molecule_type: str) -> dict[str, Any]:
    families: list[dict[str, Any]] = described["families"]
    [found] = [entry for entry in families if entry["type"] == molecule_type]
    return found


def test_describes_every_family_in_the_union_and_no_others() -> None:
    from typing import get_args

    described = catalog.describe()

    assert {entry["type"] for entry in described["families"]} == {
        member.model_fields["type"].default for member in get_args(schemas.Molecule)
    }


def test_reports_the_closed_set_of_tones_the_model_may_pick_from() -> None:
    from typing import get_args

    [tone] = [
        field
        for field in _family(catalog.describe(), "callout")["fields"]
        if field["name"] == "tone"
    ]

    assert tone["choices"] == list(get_args(schemas.CalloutTone))


def test_reports_the_bounds_validation_enforces() -> None:
    [body] = [
        field
        for field in _family(catalog.describe(), "callout")["fields"]
        if field["name"] == "body"
    ]

    expected = schemas.Callout.model_fields["body"]
    assert body["bounds"]["max"] == 420
    assert body["required"] is expected.is_required()


def test_carries_the_prose_the_model_actually_reads() -> None:
    fields = _family(catalog.describe(), "callout")["fields"]

    for field in fields:
        if field["name"] == "type":
            continue
        assert field["description"], f"{field['name']} is handed to the model undocumented"


def test_orders_type_first_and_the_shared_capabilities_last() -> None:
    names = [field["name"] for field in _family(catalog.describe(), "callout")["fields"]]

    assert names[0] == "type"
    assert names[-2:] == ["inspect", "signal"]


def test_expands_the_nested_cell_shapes() -> None:
    nested = _family(catalog.describe(), "metric_grid")["nested"]

    assert [entry["name"] for entry in nested] == ["Metric"]
    assert {field["name"] for field in nested[0]["fields"]} == {"label", "value", "sub"}


def test_renders_the_optional_total_as_a_model_that_may_be_omitted() -> None:
    [total] = [
        field
        for field in _family(catalog.describe(), "score_table")["fields"]
        if field["name"] == "total"
    ]

    assert total["type"] == "ScoreRow, or omitted"


def test_renders_a_list_of_models_as_such() -> None:
    [metrics] = [
        field
        for field in _family(catalog.describe(), "metric_grid")["fields"]
        if field["name"] == "metrics"
    ]

    assert metrics["type"] == "list of Metric"


def test_every_family_gets_its_own_specimen_surface() -> None:
    described = catalog.describe()

    surface_ids = [entry["surface_id"] for entry in described["families"]]
    assert len(set(surface_ids)) == len(surface_ids)
    assert all(surface.startswith(catalog.SURFACE_PREFIX) for surface in surface_ids)


def test_specimens_are_not_clickable() -> None:
    for family in catalog._SPECIMENS.values():
        for specimen in family:
            assert specimen.inspect is False, (
                "a gallery band that opened the review pane would question a specimen"
            )


def test_specimen_messages_are_real_a2ui_frames() -> None:
    messages = catalog.describe()["a2ui"]

    assert all("version" in message for message in messages)
    assert any("createSurface" in message for message in messages)


def test_the_summary_is_the_docstring_line_that_names_the_ds_section() -> None:
    assert _family(catalog.describe(), "callout")["summary"].startswith("DS §3.2")
