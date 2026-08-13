"""One molecule, traced from the system prompt to the pixels.

The protocol inspector shows the whole section at once, in parallel panes: what
the agent returned, what the compiler made of it, every frame that crossed the
wire. That is the right shape for diagnosing a run and the wrong shape for
explaining one to somebody. Nobody follows five molecules through four
transformations simultaneously.

So this module builds the other view: a single molecule, followed end to end,
through every stage in order. It is assembled from the real run -- the prompt
that was actually sent, the JSON the model actually returned, the sanitiser's
actual verdict, the components `a2ui.py` actually compiled -- so it explains the
system rather than illustrating it, and it cannot drift from what the system
does.

The traced molecule is chosen, not fixed: a callout when there is one, because it
carries the most fields and is the only family the sanitiser has real repairs
for. The choice is about how much of the machinery one specimen can show.
"""

from __future__ import annotations

import json
from typing import Any, Final

import a2ui
from schemas import Molecule

# The surface the final stage draws into. Its own, not the section's: the point
# being made is that a molecule is position-independent data, and the same values
# drawn a second time somewhere else is the demonstration of that.
SURFACE_ID: Final = "walkthrough"

# Families in the order they show the most machinery. A callout binds five fields
# plus both capabilities and is the one family `_sanitize` can repair; a metric
# grid binds a single nested list. When neither is present the first molecule is
# traced, because a walkthrough of nothing is worse than a walkthrough of a
# less interesting specimen.
_PREFERENCE: Final[tuple[str, ...]] = ("callout", "score_table", "phase_plan", "metric_grid")


def choose(molecules: list[Molecule]) -> int:
    """Which molecule to trace. Returns its index in `molecules`."""
    for family in _PREFERENCE:
        for index, molecule in enumerate(molecules):
            if molecule.type == family:
                return index
    return 0


def repairs(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    """What the sanitiser changed between the model's molecule and the drawn one.

    Reported as a diff rather than as a description, because the interesting case
    is the one where the list is empty: on most runs the model's output needs no
    repair at all, and a stage that says so is more convincing than a stage that
    claims a safety net exists.
    """
    changed: list[dict[str, str]] = []
    for field, old in before.items():
        new = after.get(field)
        if new != old:
            changed.append({"field": field, "was": json.dumps(old), "now": json.dumps(new)})
    return changed


def resolved(component: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
    """Each binding in a component, and what A2UI's binder resolves it to.

    This is the stage that shows what the protocol is actually for. The component
    holds no content -- every prop is a pointer -- and the values arrive from the
    data model at render time. Re-sending the data alone changes what the band
    says without touching the band.
    """
    rows: list[dict[str, Any]] = []
    for field, binding in component.items():
        if not isinstance(binding, dict) or "path" not in binding:
            continue  # `id` and `component` are the component's identity, not data
        value = values.get(field)
        rows.append(
            {
                "field": field,
                "path": binding["path"],
                # Scalars read as themselves; a list of metrics or score rows has
                # to be shown as JSON or it is not shown at all.
                "value": value if isinstance(value, (str, bool, int, float)) else None,
                "json": None if isinstance(value, (str, bool, int, float)) else json.dumps(value),
            }
        )
    return rows


def _display_surface(drawn: Molecule, index: int) -> list[dict[str, Any]]:
    """The traced molecule, drawn on a surface of its own at its real index.

    Padded rather than re-indexed. Compiling it as the only molecule would give it
    `/molecules/0/...` bindings, and a final stage that quietly renumbered the
    paths the stage above it just explained would undo the explanation. The
    leading `None`s are never bound by anything.

    The root is built here rather than by `a2ui.root_component`, which numbers its
    children from zero: this surface holds one component at an arbitrary index,
    which is a shape only a walkthrough needs.
    """
    return [
        a2ui.create_surface(SURFACE_ID),
        a2ui.update_data_model(
            SURFACE_ID, "/", {"molecules": [None] * index + [a2ui.molecule_data(drawn)]}
        ),
        a2ui.update_components(
            SURFACE_ID,
            [
                a2ui.component_for(drawn, index),
                {
                    "id": a2ui.ROOT_ID,
                    "component": a2ui.ROOT_COMPONENT,
                    "children": [f"m{index}"],
                },
            ],
        ),
    ]


def build(
    *,
    instructions: str,
    document_text: str,
    model: str,
    returned: Molecule,
    drawn: Molecule,
    index: int,
    returned_count: int,
    drawn_count: int,
) -> dict[str, Any]:
    """Assemble the trace for one molecule.

    Args:
        instructions: The standing half of the system prompt, sent to every
            document. Kept separate from the document because that split is real
            -- it is why one document's peculiarities cannot leak into another's
            analysis -- and a walkthrough that showed one concatenated blob would
            hide it.
        document_text: The half appended for this request.
        model: The model that answered it.
        returned: The molecule the model returned, before sanitising.
        drawn: The same molecule after sanitising -- what actually renders.
        index: Its position in the final list, which fixes its binding paths.
        returned_count: How many molecules the model returned.
        drawn_count: How many survived sanitising. The traced molecule is
            necessarily one of the survivors, so the stage that reports the
            sanitiser cannot show a drop by looking at it -- it has to report the
            run's totals or it implies nothing was ever discarded.

    Returns:
        The stages, plus the A2UI messages that draw `drawn` on its own surface.
    """
    before = returned.model_dump(mode="json")
    after = drawn.model_dump(mode="json")
    component = a2ui.component_for(drawn, index)

    return {
        "model": model,
        "instructions": instructions,
        "document_text": document_text,
        # The vocabulary is handed over as the response format, not as prose in
        # the prompt -- worth stating, because reading the prompt alone leaves you
        # thinking the field names were asked for in English.
        "response_format": "SectionPlan",
        "family": drawn.type,
        "component_name": a2ui.component_name(drawn.type),
        "index": index,
        "returned": before,
        "repairs": repairs(before, after),
        "drawn": after,
        # The sanitiser's two outcomes are different in kind: a repair edits a
        # field, a drop discards the whole molecule. Reported separately because a
        # panel that showed only repairs would read as "nothing was discarded".
        "returned_count": returned_count,
        "drawn_count": drawn_count,
        "dropped_count": returned_count - drawn_count,
        # The real message writes the whole model at `/`; this is the slice of it
        # that these bindings resolve against.
        "data_path": f"/molecules/{index}",
        "component": component,
        "resolved": resolved(component, after),
        "surface_id": SURFACE_ID,
        "a2ui": _display_surface(drawn, index),
    }
