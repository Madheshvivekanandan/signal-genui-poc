"""A2UI v0.9 wire format: message builders and the molecule -> A2UI compiler.

The agent still plans in the typed molecules of `schemas.py`; everything the
browser receives is emitted here as genuine A2UI v0.9 messages
(`createSurface`, `updateDataModel`, `updateComponents`) which `@a2ui/react`
renders directly. Nothing downstream of this module knows about our molecule
types -- that is what makes this a protocol boundary rather than a naming
convention.

Two rules shape the output:

1. **Data lives in the data model, not in the component tree.** Components carry
   `{"path": "/molecules/0/body"}` bindings instead of inline values, so a later
   `updateDataModel` changes what a band says without resending the band. That
   binding layer is the whole of what A2UI adds over sending our own JSON.
2. **Layout stays in the design system.** The only structural component is our
   own `MoleculeStack`, which draws `.molecule-stack` and nothing else. A2UI's
   basic catalog is deliberately *not* registered: `Column` and `Row` inject
   their own flex styles and spacing variables, which would compete with
   `signal.css` for control of the section body.

Protocol note: v0.9, not the v1.0 candidate. v0.9.1 is still the current stable
spec, `@a2ui/react` ships `v0_8` and `v0_9` entry points and no v1.0 one, so
v0.9 is the only version that renders natively today.
"""

from __future__ import annotations

import json
from typing import Any, Final

from app.schemas import Molecule

VERSION: Final = "v0.9"

# Our catalog: four components, registered by the client under this same id. It
# is an identifier, never a URL that gets fetched.
CATALOG_ID = "https://signal.rfp/catalogs/rfp-overview/v1.json"

# The section body is one long-lived surface. A fixed id means a re-run replaces
# the previous render instead of stacking a second copy beside it.
SECTION_SURFACE_ID = "rfp-overview"

# A review-pane answer that attaches molecules gets its own short-lived surface,
# one per answer -- so a second question does not overwrite the intel card the
# first one produced. Unlike the section, these ids cannot be fixed.
INSPECT_SURFACE_PREFIX = "inspect-"

ROOT_ID = "root"
ROOT_COMPONENT = "MoleculeStack"

# The one action name the client sends back. The datapoint's identity travels in
# the action context, so the server needs a single handler no matter which
# molecule -- or which tile inside a molecule -- was clicked.
INSPECT_ACTION = "inspect"

# Molecule type -> the component name in our catalog, and the data-model keys it
# binds. Adding a family is one row here, one Pydantic model, one React
# implementation.
_VIEW: dict[str, tuple[str, tuple[str, ...]]] = {
    "metric_grid": ("MetricGrid", ("metrics",)),
    "callout": ("Callout", ("tone", "lead", "body", "label", "source")),
    "score_table": ("ScoreTable", ("rows", "total")),
    "phase_plan": ("PhasePlan", ("phases",)),
    "arc_beats": ("ArcBeats", ("beats",)),
}

# DS §3: every molecule can wear `.inspect` and `.signal`, so every component
# binds them regardless of family.
CAPABILITY_FIELDS = ("inspect", "signal")


# --- message builders -----------------------------------------------------


def create_surface(surface_id: str) -> dict[str, Any]:
    """Open a surface.

    v0.9's `createSurface` carries nothing beyond the ids. Inline `components`
    and `dataModel` are a v1.0 addition and are silently dropped here, which
    would leave the surface stuck empty -- content always arrives as separate
    update messages.
    """
    return {
        "version": VERSION,
        "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID},
    }


def update_components(surface_id: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    """Add or replace components by id. Ids not mentioned are left alone."""
    return {
        "version": VERSION,
        "updateComponents": {"surfaceId": surface_id, "components": components},
    }


# `value` is `Any` by the protocol's own definition: `updateDataModel` writes
# arbitrary JSON at a pointer, so narrowing it here would narrow A2UI.
def update_data_model(surface_id: str, path: str, value: Any) -> dict[str, Any]:  # noqa: ANN401
    """Write `value` at `path` in the surface's data model.

    Every call here writes the whole model at `/`. Writing a single index
    (`/molecules/2`) would depend on how the client resolves a JSON-Pointer
    index against an array that is still growing, and the payloads at this size
    are a few kilobytes -- not worth the ambiguity.
    """
    return {
        "version": VERSION,
        "updateDataModel": {"surfaceId": surface_id, "path": path, "value": value},
    }


def bind(path: str) -> dict[str, str]:
    """A data-model binding -- the `{"path": ...}` form A2UI resolves at render."""
    return {"path": path}


# `deleteSurface`, A2UI's fourth server-to-client message, has no builder: the
# only thing that closes a surface here is the user, and the client builds that
# message itself rather than asking the server for permission.


# --- the compiler ---------------------------------------------------------


def molecule_data(molecule: Molecule) -> dict[str, Any]:
    """One molecule's values, as stored in the surface data model.

    `type` is kept even though no component binds it: the data model is the
    thing you read when a render looks wrong, and a list of untyped bags of
    fields is materially harder to debug.
    """
    return molecule.model_dump(mode="json")


def component_for(molecule: Molecule, index: int) -> dict[str, Any]:
    """One molecule -> the single catalog component that draws it.

    Molecules are not decomposed into Cards and Columns. A metric grid is one
    `MetricGrid`, because DS §3.1's grid and §3.3's row grids *are* the spec --
    rebuilding them out of A2UI primitives would move layout decisions out of
    the design system and into this compiler.
    """
    view_name, fields = _VIEW[molecule.type]
    component: dict[str, Any] = {"id": f"m{index}", "component": view_name}
    for field in (*fields, *CAPABILITY_FIELDS):
        component[field] = bind(f"/molecules/{index}/{field}")
    return component


def component_name(molecule_type: str) -> str:
    """The catalog component that draws a molecule family.

    Exposed so the vocabulary endpoint can report the mapping without reaching
    into `_VIEW`, which is this module's own business.

    Raises:
        KeyError: If the family has no view -- a `_VIEW` row was forgotten.
    """
    return _VIEW[molecule_type][0]


def directness_cost(molecules: list[Molecule]) -> dict[str, int]:
    """What the model would have had to write if it emitted A2UI itself.

    A2UI's documented default is for the model to generate the protocol messages
    directly. This POC does not: the model returns typed molecules and this
    module compiles them. The argument for compiling is partly that the component
    tree is 100% derivable from `type` -- so measure it rather than assert it.

    `typed` is the JSON the model actually emits. `direct` is that same data model
    plus the component tree it would additionally have to write, correctly, on
    every generation. The difference between the two is exactly the compiler's
    output.

    Returns:
        Byte counts for both, and the component and binding-path totals the model
        is spared. Counts, not opinions -- the panel that shows this draws its own
        conclusion.
    """
    components = component_tree(molecules)
    values = json.dumps(data_model(molecules), separators=(",", ":"))
    tree = json.dumps(components, separators=(",", ":"))

    # Every `{"path": ...}` in the tree. `root`'s children are ids rather than
    # bindings, so this counts only what a binder actually resolves.
    bindings = sum(
        1 for component in components for value in component.values() if isinstance(value, dict)
    )

    return {
        "typed_bytes": len(values),
        "direct_bytes": len(values) + len(tree),
        "components": len(components),
        "bindings": bindings,
    }


def root_component(count: int) -> dict[str, Any]:
    """The stack that holds `count` molecules, in order."""
    return {
        "id": ROOT_ID,
        "component": ROOT_COMPONENT,
        "children": [f"m{index}" for index in range(count)],
    }


def component_tree(molecules: list[Molecule]) -> list[dict[str, Any]]:
    """Every component needed to draw `molecules`, root included."""
    components = [component_for(molecule, index) for index, molecule in enumerate(molecules)]
    components.append(root_component(len(molecules)))
    return components


def data_model(molecules: list[Molecule]) -> dict[str, Any]:
    """The surface data model the component bindings resolve against."""
    return {"molecules": [molecule_data(molecule) for molecule in molecules]}


def open_surface(surface_id: str) -> list[dict[str, Any]]:
    """Open a surface and seed an empty data model.

    The empty `molecules` list matters: a component whose binding resolves
    against a missing model logs a resolution failure, and the first molecule's
    components can land before its data if the two are sent out of order.
    """
    return [
        create_surface(surface_id),
        update_data_model(surface_id, "/", {"molecules": []}),
    ]


def append_molecule(surface_id: str, molecules: list[Molecule]) -> list[dict[str, Any]]:
    """Messages that add the newest molecule in `molecules` to the surface.

    Data first, then components, so no binding is ever live against a model that
    does not yet hold its value. Only the new component and the root are sent --
    A2UI addresses components by id, so the bands already on screen are left
    untouched and do not repaint.
    """
    index = len(molecules) - 1
    return [
        update_data_model(surface_id, "/", data_model(molecules)),
        update_components(
            surface_id,
            [component_for(molecules[index], index), root_component(len(molecules))],
        ),
    ]


def replace_surface(surface_id: str, molecules: list[Molecule]) -> list[dict[str, Any]]:
    """Replace a surface's entire contents with `molecules`.

    This is the authoritative pass. It deliberately re-sends everything the
    optimistic pass already sent: the point is that a molecule the first pass
    parsed from half-written JSON is overwritten by the validated, sanitised one
    before the user can act on it. Same message types, different source of
    truth -- do not collapse the two callers into one.
    """
    return [
        update_data_model(surface_id, "/", data_model(molecules)),
        update_components(surface_id, component_tree(molecules)),
    ]


def full_surface(surface_id: str, molecules: list[Molecule]) -> list[dict[str, Any]]:
    """A complete surface as one batch, for content that is not streamed."""
    return [create_surface(surface_id), *replace_surface(surface_id, molecules)]
