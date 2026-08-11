"""The RFP Overview agent: a document in, a stream of molecules out.

The generation is streamed twice over, which is the whole reason this feels like
an interface building itself rather than a spinner followed by a page:

* **Optimistically**, from the model's partially-parsed JSON. The moment one
  molecule is provably finished it is emitted, so the metric grid is on screen
  while the model is still writing the third callout.
* **Authoritatively**, once the stream closes. The completed object is validated
  and sanitised, then the whole section is re-sent as a replace. A molecule the
  optimistic pass got wrong or skipped is corrected before the user can click it.

The model chooses which molecule family to use, how many instances, the content,
and the `inspect`/`signal` capability flags. It does not choose markup, classes,
colours, or the page layout -- the design system owns those, and the frontend
registry is the only place a molecule type becomes DOM.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Generator, Iterator, Literal, NamedTuple

from openai import OpenAI
from pydantic import TypeAdapter, ValidationError

import schemas
from rfp_document import rfp_for_prompt
from schemas import ErrorCode, InspectAnswer, Molecule, SectionPlan, Turn

logger = logging.getLogger("signal.agent")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_molecule_adapter: TypeAdapter[Molecule] = TypeAdapter(Molecule)

SYSTEM_PROMPT = f"""You are the RFP Overview agent inside Signal, a tool that helps an \
agency decide whether to bid on an RFP and how. You read the RFP below and return a \
structured read of it as a small set of design-system molecules.

You are not writing prose for a chat window. You are choosing components. The product \
renders exactly what you return, so the choice of molecule IS the design decision.

WHAT TO PRODUCE

Open with one metric_grid of exactly 4 tiles carrying YOUR VERDICT on the bid. These are \
judgements, not lookups:
- a recommendation -- one word, e.g. "Pursue", "Pass", "Pursue with conditions";
- the money -- your estimated budget range, since the document does not state one;
- the fit -- High, Medium or Low, against an agency that sells outcomes-led engagements;
- the clock -- how long we have to respond.

Do NOT spend metric tiles restating the header. The client name, the sector and the \
reference number are already on the page above you; a tile that repeats them is a wasted \
tile.

Then a small number of callouts covering what the RFP actually asks for, how the process \
runs, what the commercial picture is, and what it requires of us. Use a score_table only \
if the document gives you real criteria to score against; this one does not give you \
weightings, so you almost certainly should not.

At most {schemas.MAX_MOLECULES} molecules in total. Fewer, denser molecules beat more \
thin ones.

CHOOSING THE BAND

The callout's tone is the only thing carrying the category, so it has to be right:
- context: a fact or a quote from the document. Most of your callouts.
- recommendation: what we should do about it. Sparing -- one, maybe two.
- risk: a gap, an unstated term, an inference you are not confident in.

CAPABILITIES -- these are not optional, and a section with none of them is wrong

Every molecule carries `inspect` and `signal`. They are how a partner interrogates your \
work, so you must set them deliberately rather than leaving them off.

inspect = true on the metric_grid, and on every callout that carries a judgement, an \
estimate, or a claim traced to a section. In practice that is most of what you produce. \
Set it false only on a callout that is a flat restatement of the document with nothing to \
challenge.

signal = true where the document genuinely leaves you unable to answer and a human has to \
weigh in: a figure you estimated rather than read, a term the RFP declines to state, a \
material question it leaves open. Any tile or band whose content you inferred rather than \
found MUST be signalled -- presenting an estimate as though it were sourced is the one \
failure that actually costs the user money.

One or two signals, never more. A section where everything is flagged has flagged nothing.

DISCIPLINE

- Cite sections as the document numbers them ("§4", "§5(a)"). Never invent a section.
- Every figure is either stated in the document or clearly marked as your estimate. If \
you estimate a budget, say what it is derived from and band it as a risk, because the \
document does not state one.
- Quote the RFP's own language where it is doing work ("competitive market rates", \
"commercial growth, not channel reporting"). The partner is going to be quoted back at.
- Write in the product's voice: short, declarative, no hedging, no "it appears that".
- Never pad to fill the molecule budget.

THE RFP
{rfp_for_prompt()}
"""

INSPECT_SYSTEM_PROMPT = f"""You are the Signal Review agent. The user has clicked one \
datapoint in the RFP Overview and is asking about it -- where it came from, why it is \
flagged, or whether it is right.

Answer only from the RFP below. Quote the section that settles it. If the document does \
not settle it, say so plainly and say what would -- do not fill the gap with a plausible \
guess, because the user is deciding whether to trust the section.

You may attach at most two molecules when a component answers better than a sentence: \
an intel-card callout (tone context, with label and source) to show an attribution, or a \
metric_grid to lay out figures being compared. Attach nothing when prose is enough, \
which is most of the time.

Keep it to a few sentences.

THE RFP
{rfp_for_prompt()}
"""


class Event(NamedTuple):
    """One thing to push down the SSE connection."""

    kind: Literal["molecule", "section", "answer", "meta"]
    payload: dict


class Clock:
    """Monotonic stopwatch for the timings the demo reports on screen.

    Harman asked twice whether this lags. The honest answer is a number, so every
    stream carries its own timings rather than leaving it to a feeling.

    `mark_molecule` is deliberately separate from `elapsed_ms`: time-to-first-
    molecule is the number that matters here, and if merely reading the clock
    recorded it, a run that emitted nothing optimistically would report its
    fallback as a fast first paint.
    """

    def __init__(self) -> None:
        self._start = time.monotonic()
        self._first_molecule_ms: int | None = None

    def elapsed_ms(self) -> int:
        """Milliseconds since the stream opened."""
        return int((time.monotonic() - self._start) * 1000)

    def mark_molecule(self) -> int:
        """Record and return the elapsed time at a molecule emission."""
        elapsed = self.elapsed_ms()
        if self._first_molecule_ms is None:
            self._first_molecule_ms = elapsed
        return elapsed

    @property
    def first_molecule_ms(self) -> int | None:
        """Time to the first optimistically-emitted molecule, or None if there was none."""
        return self._first_molecule_ms


_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Lazily build the OpenAI client so the app still boots without a key."""
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from the environment
    return _client


def _sanitize(molecule: Molecule) -> Molecule:
    """Repair what is repairable in a validated molecule; raise on the rest.

    Validation already guarantees the shape. This is about the handful of states
    that are structurally legal but wrong on screen.

    Raises:
        ValueError: If the molecule cannot be drawn at all.
    """
    if isinstance(molecule, schemas.Callout):
        # DS §3.2: the intel header is a label *and* an italic source line. A
        # source with no label renders as an orphan line above the body, so the
        # header is all-or-nothing.
        if molecule.source and not molecule.label:
            molecule = molecule.model_copy(update={"source": ""})
        # A band needs either a bolded lead or a label to open it; a bare
        # paragraph in a banded surface reads as a styling accident.
        if not molecule.lead and not molecule.label:
            raise ValueError("callout has neither lead nor label")

    if isinstance(molecule, schemas.ScoreTable):
        # The total row reuses the row grid so the columns align; a total that
        # does not line up with any rows is worse than no total.
        if molecule.total is not None and not molecule.rows:
            raise ValueError("score_table has a total but no rows")

    return molecule


def _parse_partial(raw: Any) -> Molecule | None:
    """Validate one molecule out of a partially-streamed object.

    `raw` is `Any` because it is the SDK's partial-parse snapshot: at this point
    in the stream it may be a half-built dict, a scalar, or absent entirely.
    Narrowing it is exactly this function's job.

    Returns:
        The sanitised molecule, or None if it is not yet whole -- in which case
        the authoritative pass emits it properly a moment later.
    """
    if not isinstance(raw, dict) or not raw.get("type"):
        return None
    try:
        return _sanitize(_molecule_adapter.validate_python(raw))
    except (ValidationError, ValueError):
        return None


def _stream_section(clock: Clock) -> Generator[Event, None, SectionPlan]:
    """Stream the model, emitting molecules optimistically; return the whole plan.

    Returns:
        The completed, validated plan, for the caller's authoritative pass.

    Raises:
        ValueError: If the model refused, or returned nothing parseable.
    """
    emitted = 0

    with get_client().beta.chat.completions.stream(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        response_format=SectionPlan,
        temperature=0.2,
    ) as stream:
        for event in stream:
            if event.type != "content.delta" or not event.parsed:
                continue

            raw = event.parsed.get("molecules")
            if not isinstance(raw, list):
                continue

            # A molecule is only provably finished once the next one has started,
            # so the last one in the snapshot is always left to the caller.
            for index in range(emitted, len(raw) - 1):
                molecule = _parse_partial(raw[index])
                if molecule is None:
                    break
                emitted = index + 1
                yield Event(
                    "molecule",
                    {
                        "index": index,
                        "molecule": molecule.model_dump(),
                        "at_ms": clock.mark_molecule(),
                    },
                )

        completion = stream.get_final_completion()

    choice = completion.choices[0]
    if choice.message.refusal:
        raise ValueError(f"model refused: {choice.message.refusal}")
    if choice.message.parsed is None:
        raise ValueError("model returned no parseable output")
    return choice.message.parsed


def _usable(molecules: list[Molecule]) -> list[Molecule]:
    """Sanitise a plan's molecules, dropping any that cannot be drawn.

    One unusable molecule does not sink the section -- a broken callout next to a
    good metric grid should cost the callout, not the answer.
    """
    usable: list[Molecule] = []
    for molecule in molecules[: schemas.MAX_MOLECULES]:
        try:
            usable.append(_sanitize(molecule))
        except ValueError as exc:
            logger.warning("dropping unusable molecule: %s", exc)
    return usable


# Every user-facing failure, in one place. The copy is deliberately generic: an
# upstream exception message can carry a partial API key or other internals, and
# whatever lands in `body` is rendered verbatim in the browser. Diagnostics go to
# the log, not to the client.
FALLBACK_COPY: dict[ErrorCode, tuple[str, str]] = {
    "missing_api_key": (
        "Missing API key.",
        "Set OPENAI_API_KEY in the server's environment and restart it, then reload. "
        "Locally that is backend/.env; under Docker it is the .env next to compose.yaml.",
    ),
    "schema_validation_failed": (
        "Could not render this section.",
        "The agent returned something outside the molecule catalog. The server log has the "
        "validation error.",
    ),
    "unusable_molecules": (
        "Could not render this section.",
        "Nothing renderable came back from the agent. Try reloading.",
    ),
    "upstream_error": (
        "Could not reach the agent.",
        "The section could not be generated. Check the server log and try again.",
    ),
}


def _fallback(error: ErrorCode, clock: Clock) -> Iterator[Event]:
    """A renderable stand-in, so no failure leaves the section empty.

    The fallback is itself a molecule -- a risk-toned callout -- rather than a
    special-cased error box. If the renderer can draw the failure state, the
    renderer is the only thing that ever draws.
    """
    lead, body = FALLBACK_COPY[error]
    notice = schemas.Callout(tone="risk", lead=lead, body=body)
    yield Event(
        "section",
        {
            "summary": "This section could not be generated.",
            "molecules": [notice.model_dump()],
        },
    )
    yield Event(
        "meta",
        {
            "ok": False,
            "error": error,
            "total_ms": clock.elapsed_ms(),
            "first_molecule_ms": clock.first_molecule_ms,
        },
    )


def run_overview() -> Iterator[Event]:
    """Stream the RFP Overview section. Never raises: every path yields a section."""
    clock = Clock()

    if not os.getenv("OPENAI_API_KEY"):
        yield from _fallback("missing_api_key", clock)
        return

    try:
        plan = yield from _stream_section(clock)
    except ValidationError as exc:
        logger.warning("agent output failed validation: %s", exc)
        yield from _fallback("schema_validation_failed", clock)
        return
    except Exception:  # network, auth, rate limit, refusal, anything upstream
        logger.exception("overview generation failed")
        yield from _fallback("upstream_error", clock)
        return

    final = _usable(plan.molecules)
    if not final:
        yield from _fallback("unusable_molecules", clock)
        return

    yield Event(
        "section",
        {
            "summary": plan.summary,
            "molecules": [molecule.model_dump() for molecule in final],
        },
    )
    yield Event(
        "meta",
        {
            "ok": True,
            "error": None,
            "total_ms": clock.elapsed_ms(),
            "first_molecule_ms": clock.first_molecule_ms,
            "molecule_count": len(final),
            "signal_count": sum(1 for molecule in final if molecule.signal),
        },
    )


def run_inspect(question: str, subject: str, history: list[Turn]) -> Iterator[Event]:
    """Answer a review-pane question about one inspected molecule.

    Args:
        question: What the user typed.
        subject: A short description of the molecule they clicked, so the model
            knows what "this" refers to without the client resending the tree.
        history: Prior turns in this review conversation.

    Yields:
        One `answer` event, then `meta`. Never raises.
    """
    clock = Clock()

    if not os.getenv("OPENAI_API_KEY"):
        _, body = FALLBACK_COPY["missing_api_key"]
        yield Event("answer", {"answer": body, "molecules": []})
        yield Event(
            "meta",
            {"ok": False, "error": "missing_api_key", "total_ms": clock.elapsed_ms()},
        )
        return

    replayed = [{"role": turn.role, "content": turn.content} for turn in history]
    try:
        completion = get_client().beta.chat.completions.parse(
            model=MODEL,
            messages=[
                {"role": "system", "content": INSPECT_SYSTEM_PROMPT},
                {"role": "system", "content": f"The user is asking about: {subject}"},
                *replayed,
                {"role": "user", "content": question},
            ],
            response_format=InspectAnswer,
            temperature=0.2,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("model returned no parseable output")
    except Exception:  # network, auth, rate limit, refusal, anything upstream
        logger.exception("inspect answer failed")
        _, body = FALLBACK_COPY["upstream_error"]
        yield Event("answer", {"answer": body, "molecules": []})
        yield Event(
            "meta",
            {"ok": False, "error": "upstream_error", "total_ms": clock.elapsed_ms()},
        )
        return

    yield Event(
        "answer",
        {
            "answer": parsed.answer,
            "molecules": [molecule.model_dump() for molecule in _usable(parsed.molecules)],
        },
    )
    yield Event("meta", {"ok": True, "error": None, "total_ms": clock.elapsed_ms()})
