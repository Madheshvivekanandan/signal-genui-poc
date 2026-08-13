"""The molecule vocabulary, described and demonstrated.

What is a component "listed to the LLM"? Two things, and this module serves both
from their real source rather than from a copy:

1. **The schema.** `response_format=SectionPlan` hands the model the JSON Schema
   of the `Molecule` union -- every field name, its type, its closed set of
   allowed values, its length bounds, and the `Field(description=...)` prose. The
   model cannot return anything outside it. The field tables here are derived
   from `schemas.py` by introspection, so they cannot drift from what is actually
   sent: change a bound in `schemas.py` and this endpoint reports the new one.

2. **The component itself.** A name and a field list do not tell you what a
   `callout` *is*. So each family also ships specimens -- real `Molecule`
   instances, compiled through the same `a2ui.py` used for the agent's own
   output, drawn by the same catalog in the browser. The gallery is not a mock
   of the components; it is the components.

Specimens are deliberately `inspect: false`. The flag is part of the vocabulary
and the field table documents it, but a gallery band that opened the review pane
would send a question about a specimen to the model, grounded in whatever
document happened to be selected.
"""

from __future__ import annotations

from types import UnionType
from typing import Any, Final, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

import a2ui
import schemas
from schemas import Callout, MetricGrid, Molecule, ScoreRow, ScoreTable

# One surface per family, so the page can draw each specimen set beside its own
# field table instead of as one undifferentiated stack.
SURFACE_PREFIX: Final = "catalog-"

# The families, in the order the design system numbers them (DS §3.1-§3.3).
_FAMILIES: Final[tuple[type[BaseModel], ...]] = (MetricGrid, Callout, ScoreTable)

# DS §3: these two cut across every family, so they are listed last in each table
# rather than interleaved with the fields that differ.
_CAPABILITIES: Final[tuple[str, ...]] = ("inspect", "signal")

_SCALAR_NAMES: Final[dict[Any, str]] = {str: "string", bool: "boolean", int: "integer"}


def _summary(model: type[BaseModel]) -> str:
    """The first line of a model's docstring, which names its DS section."""
    doc = (model.__doc__ or "").strip()
    return doc.split("\n", 1)[0]


def _type_label(annotation: Any) -> tuple[str, list[str]]:
    """Render an annotation as the constraint the model has to satisfy.

    Returns:
        The readable type, and the closed set of allowed values if there is one.
    """
    origin = get_origin(annotation)

    # A closed set. The single most important thing on this page: the model picks
    # a meaning from a fixed list, it does not invent one.
    if origin is Literal:
        return "string", [str(choice) for choice in get_args(annotation)]

    if origin is list:
        (item,) = get_args(annotation)
        label, _ = _type_label(item)
        return f"list of {label}", []

    # `ScoreRow | None` is the only union in the vocabulary.
    if origin in (UnionType, Union):
        members = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(members) == 1:
            label, choices = _type_label(members[0])
            return f"{label}, or omitted", choices

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.__name__, []

    return _SCALAR_NAMES.get(annotation, getattr(annotation, "__name__", "value")), []


def _bounds(field: FieldInfo) -> dict[str, int]:
    """The length bounds validation enforces, as `annotated_types` records them."""
    bounds: dict[str, int] = {}
    for entry in field.metadata:
        minimum = getattr(entry, "min_length", None)
        maximum = getattr(entry, "max_length", None)
        if minimum is not None:
            bounds["min"] = minimum
        if maximum is not None:
            bounds["max"] = maximum
    return bounds


def _sort_key(name: str) -> int:
    """`type` first, the family's own fields next, the shared capabilities last."""
    if name == "type":
        return 0
    return 2 if name in _CAPABILITIES else 1


def _fields_of(model: type[BaseModel]) -> list[dict[str, Any]]:
    """One row per field the model may set, with the description it is given."""
    rows: list[dict[str, Any]] = []
    for name, field in model.model_fields.items():
        label, choices = _type_label(field.annotation)
        rows.append(
            {
                "name": name,
                "type": label,
                "choices": choices,
                "bounds": _bounds(field),
                "required": field.is_required(),
                # The prose the model actually reads: Pydantic puts this in the
                # JSON Schema, and the JSON Schema is the response format.
                "description": field.description or "",
            }
        )
    return sorted(rows, key=lambda row: _sort_key(row["name"]))


def _referenced_models(annotation: Any) -> list[type[BaseModel]]:
    """Every Pydantic model an annotation reaches, e.g. `Metric` in `list[Metric]`."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    found: list[type[BaseModel]] = []
    for argument in get_args(annotation):
        found.extend(_referenced_models(argument))
    return found


def _nested_of(model: type[BaseModel]) -> list[dict[str, Any]]:
    """The sub-models a family's fields reference.

    `list of Metric` is opaque on its own, and the cell shapes are where most of
    the design system's §3.1 and §3.3 spec actually lives.
    """
    seen: dict[str, type[BaseModel]] = {}
    for field in model.model_fields.values():
        for referenced in _referenced_models(field.annotation):
            seen.setdefault(referenced.__name__, referenced)
    return [
        {"name": name, "summary": _summary(sub), "fields": _fields_of(sub)}
        for name, sub in seen.items()
    ]


# Specimens. The content is chosen to describe the field it occupies -- a gallery
# band that says what a band is for teaches more than one carrying invented
# analysis, and it cannot be mistaken for a real read of a document.
_SPECIMENS: Final[dict[str, list[Molecule]]] = {
    "metric_grid": [
        MetricGrid(
            metrics=[
                schemas.Metric(
                    label="Recommendation", value="Pursue", sub="A verdict, in one word."
                ),
                schemas.Metric(
                    label="Est. budget", value="$180-220K", sub="The money, as the document states it."
                ),
                schemas.Metric(
                    label="Fit for agency", value="High", sub="Judgement, not a lookup."
                ),
                schemas.Metric(label="Timeline", value="14 days", sub="The clock."),
            ],
        )
    ],
    "callout": [
        Callout(
            tone="context",
            label="Budget signals",
            source="Opportunity document §4",
            body=(
                "A fact drawn from the document. Navy line. A label and a source together "
                "add the intel header row above this text."
            ),
        ),
        Callout(
            tone="recommendation",
            lead="Recommendation.",
            body=(
                "What to do about it. Teal line. The bolded phrase that opens the band is the "
                "lead; sparing, one or two per section."
            ),
        ),
        Callout(
            tone="risk",
            lead="Budget not stated.",
            signal=True,
            body=(
                "A gap, an unstated term, or an inference. Coral line. This one also carries "
                "signal: true, which puts it in the review queue."
            ),
        ),
    ],
    "score_table": [
        ScoreTable(
            rows=[
                ScoreRow(
                    name="Clinical safety",
                    weight="30%",
                    score="4.5",
                    band="high",
                    note="The note column carries the reasoning.",
                ),
                ScoreRow(
                    name="Integration",
                    weight="25%",
                    score="3.0",
                    band="mid",
                    note="Band colours the figure: low, mid or high.",
                ),
                ScoreRow(
                    name="Track record",
                    weight="15%",
                    score="2.0",
                    band="low",
                    note="The agent states the band; the stylesheet owns the colour.",
                ),
            ],
            total=ScoreRow(
                name="Weighted total",
                weight="100%",
                score="3.4",
                band="mid",
                note="The total reuses the row grid, so the columns line up.",
            ),
        )
    ],
}


def describe() -> dict[str, Any]:
    """The whole vocabulary: what the model may return, and what it looks like.

    Returns:
        The families with their field tables, plus the A2UI messages that draw
        one specimen surface per family.
    """
    families: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []

    for model in _FAMILIES:
        molecule_type = model.model_fields["type"].default
        surface_id = f"{SURFACE_PREFIX}{molecule_type}"
        messages.extend(a2ui.full_surface(surface_id, _SPECIMENS[molecule_type]))
        families.append(
            {
                "type": molecule_type,
                "component": a2ui.component_name(molecule_type),
                "summary": _summary(model),
                "surface_id": surface_id,
                "fields": _fields_of(model),
                "nested": _nested_of(model),
            }
        )

    return {
        "max_molecules": schemas.MAX_MOLECULES,
        "families": families,
        "a2ui": messages,
    }
