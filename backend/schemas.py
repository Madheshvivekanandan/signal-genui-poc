"""The agent's vocabulary: the molecules it may choose, and nothing else.

This module is the contract at the centre of the POC. The model does not write
markup, class names, colours or layout -- it returns a validated list of
*molecule instances* drawn from the Signal design system's §3, and the frontend
owns how each one is drawn. Anything the model emits that is not in this union
fails validation and never reaches the browser.

Three families are implemented, chosen because together they are the whole
visible surface of the RFP Overview screen:

* `metric_grid`  -- DS §3.1, the top-line facts row.
* `callout`      -- DS §3.2, the banded component. One component, three line
                    colours, optional intel header.
* `score_table`  -- DS §3.3, the score row family with its aligned total.

Two capabilities cut across all of them, because the design system says they do
(§3: "most molecules can wear `.inspect` and `.signal`"): `inspect` makes the
molecule a clickable datapoint that opens the review pane, and `signal` puts it
in the review queue and turns its band coral. They are modelled on the base
class rather than per-family for exactly that reason.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Bounds exist so a runaway generation cannot produce a section that scrolls for
# a screen and a half. They are also quoted into the system prompt, so the model
# is told the same limits that validation enforces.
MAX_MOLECULES = 6
MIN_METRICS = 3
MAX_METRICS = 4
MAX_SCORE_ROWS = 6

# DS §3.2. The line colour alone carries the category, so this is a closed set
# of *meanings*, not of colours -- the frontend maps meaning to class.
CalloutTone = Literal["context", "recommendation", "risk"]

# DS §3.3 score rows colour the figure by band. The model states the band it
# means rather than computing a hex value.
ScoreBand = Literal["low", "mid", "high"]

ErrorCode = Literal[
    "missing_api_key",
    "schema_validation_failed",
    "unusable_molecules",
    "upstream_error",
]


class Strict(BaseModel):
    """Reject unknown fields everywhere.

    A hallucinated key is a signal the prompt and the schema have drifted apart,
    and it should surface in the log as a validation error rather than being
    silently dropped on the floor.
    """

    model_config = ConfigDict(extra="forbid")


class MoleculeBase(Strict):
    """Fields every molecule carries, per DS §3."""

    inspect: bool = Field(
        default=False,
        description=(
            "Make this a clickable datapoint that opens the review pane. Set it when the "
            "content invites a 'how did you get this' -- a number, a judgement, a claim "
            "traced to the document. Not on plain restatements of fact."
        ),
    )
    signal: bool = Field(
        default=False,
        description=(
            "Put this in the review queue and band it coral. Set it only when the item "
            "genuinely needs the user's input or attention -- an unstated budget, a "
            "low-confidence inference, a risk. Two per section at the very most."
        ),
    )


class Metric(Strict):
    """One cell of DS §3.1. Label 14/caps, value 17/600, sub 15."""

    label: str = Field(
        max_length=28, description="Short caps label, e.g. 'Est. budget'. Not a sentence."
    )
    value: str = Field(
        max_length=40,
        description=(
            "The figure itself, pre-formatted for display: '$180-220K', '14 days', 'Pursue'. "
            "A string because these are as often verdicts as numbers."
        ),
    )
    sub: str = Field(
        default="",
        max_length=120,
        description="One short line of context under the value. Empty if the value speaks for itself.",
    )


class MetricGrid(MoleculeBase):
    """DS §3.1 -- top-line facts. Grids of 3 or 4, no surface of its own."""

    type: Literal["metric_grid"] = "metric_grid"
    metrics: list[Metric] = Field(min_length=MIN_METRICS, max_length=MAX_METRICS)


class Callout(MoleculeBase):
    """DS §3.2 -- the one banded component.

    White-tint surface, a coloured left line, squared left corner, navy text.
    `tone` picks the line; `label`/`source` add the intel header row when the
    statement is sourced from a document.
    """

    type: Literal["callout"] = "callout"
    tone: CalloutTone = Field(
        description=(
            "context = fact or intelligence drawn from a source (navy line). "
            "recommendation = what to do, or a confirmation (teal line). "
            "risk = a risk, gap, or unreviewed inference (coral line)."
        )
    )
    lead: str = Field(
        default="",
        max_length=48,
        description=(
            "The bolded verdict that opens the band -- two or three words, ending in a full "
            "stop: 'Recommendation.', 'No warm connection.' Part of the product's voice. "
            "Leave empty on intel cards that carry a label instead."
        ),
    )
    body: str = Field(
        min_length=1,
        max_length=420,
        description="The reasoning, in the product's voice. One or two sentences.",
    )
    label: str = Field(
        default="",
        max_length=32,
        description=(
            "Intel header category, e.g. 'Budget signals', 'Timeline & process'. Set this "
            "together with `source` when the statement is traceable to a document."
        ),
    )
    source: str = Field(
        default="",
        max_length=90,
        description=(
            "Italic attribution under the label: 'Opportunity document §4', "
            "'Investor Day 2025'. Only ever a source you were actually given."
        ),
    )


class ScoreRow(Strict):
    """One row of DS §3.3's score table. Grid is 160px 50px 60px 1fr."""

    name: str = Field(max_length=32, description="Criterion name, e.g. 'Win probability'.")
    weight: str = Field(max_length=8, description="Weight as shown, e.g. '25%'.")
    score: str = Field(max_length=8, description="Score as shown, e.g. '3.5'.")
    band: ScoreBand = Field(default="mid", description="Colours the figure: low, mid or high.")
    note: str = Field(
        default="", max_length=160, description="The rationale. This column carries the reasoning."
    )


class ScoreTable(MoleculeBase):
    """DS §3.3 -- scoring rows plus an aligned total that reuses the grid."""

    type: Literal["score_table"] = "score_table"
    rows: list[ScoreRow] = Field(min_length=1, max_length=MAX_SCORE_ROWS)
    total: ScoreRow | None = Field(
        default=None,
        description="The total row. Reuses the row grid exactly so the columns line up.",
    )


# A plain union, deliberately NOT `Annotated[..., Field(discriminator="type")]`.
# A discriminated union serialises to JSON Schema as `oneOf`, and the structured-
# outputs API rejects it outright:
#
#   400 Invalid schema for response_format 'SectionPlan':
#       In context=('properties','molecules','items'), 'oneOf' is not permitted.
#
# A plain union emits `anyOf`, which is accepted. Each member still carries a
# distinct `type` literal, so Pydantic's smart-union matching resolves the family
# unambiguously -- the cost is only that a validation failure reports against the
# whole union rather than naming one family.
Molecule = MetricGrid | Callout | ScoreTable


class SectionPlan(Strict):
    """One agent's structured answer for one accordion section.

    This is the whole of what the model returns. `summary` is the line under the
    section heading; `molecules` is the section body.
    """

    summary: str = Field(
        max_length=200,
        description=(
            "The line under the section heading -- what this section is and how to read it. "
            "One sentence."
        ),
    )
    molecules: list[Molecule] = Field(min_length=1, max_length=MAX_MOLECULES)


class InspectAnswer(Strict):
    """The review pane's reply when the user asks about one inspected molecule.

    Prose plus, optionally, molecules -- so an answer about a source can render
    as a real intel card rather than a paragraph describing one.
    """

    answer: str = Field(max_length=900, description="The reply, in the product's voice.")
    molecules: list[Molecule] = Field(
        default_factory=list,
        max_length=2,
        description="Optional supporting molecules, e.g. an intel card naming the source.",
    )


class Turn(Strict):
    """One replayed message of review-pane conversation."""

    role: Literal["user", "assistant"]
    content: str
