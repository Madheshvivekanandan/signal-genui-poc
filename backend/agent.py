"""The RFP Overview agent: a document in, a stream of A2UI messages out.

The generation is streamed twice over, which is the whole reason this feels like
an interface building itself rather than a spinner followed by a page:

* **Optimistically**, from the model's partially-parsed JSON. The moment one
  molecule is provably finished it is compiled to A2UI and pushed, so the metric
  grid is on screen while the model is still writing the third callout.
* **Authoritatively**, once the stream closes. The completed object is validated
  and sanitised, then the whole surface is re-sent as a replace. A molecule the
  optimistic pass got wrong or skipped is corrected before the user can click it.

The model chooses which molecule family to use, how many instances, the content,
and the `inspect`/`signal` capability flags. It does not choose markup, classes,
colours, or the page layout -- the design system owns those.

This module never emits a molecule to the client. It plans in the typed
molecules of `schemas.py` and hands them to `a2ui.py`, which is the only thing
that speaks to the browser. The wire format is A2UI v0.9.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Generator, Iterator, Literal, NamedTuple
from uuid import uuid4

from openai import OpenAI
from pydantic import TypeAdapter, ValidationError

import a2ui
import schemas
import walkthrough
from documents import Document
from schemas import ErrorCode, InspectAnswer, Molecule, SectionPlan, Turn

logger = logging.getLogger("signal.agent")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_molecule_adapter: TypeAdapter[Molecule] = TypeAdapter(Molecule)

# The prompts are built in two halves: a document-agnostic base, assembled once at
# import, plus the document appended per request. That split is not cosmetic -- the
# earlier version embedded one RFP and, with it, instructions written about that
# RFP ("this one does not give you weightings, so you almost certainly should not").
# Those instructions travelled to every other document and suppressed a whole
# molecule family. An agent that analyses documents cannot carry opinions about one.

SECTION_PROMPT_BASE = f"""You are the document analyst inside Signal, a tool that helps \
an agency decide whether to bid on an opportunity and how. You read the document below \
and return a structured read of it as design-system molecules.

You are not writing prose for a chat window. You are choosing components. The product \
renders exactly what you return, so the choice of molecule IS the design decision.

WHAT TO PRODUCE

There is no fixed opening and no house shape. Two documents that establish different \
things must not produce the same composition -- if your answer would look the same \
whatever you had just read, you have templated it instead of analysing it.

1. A metric_grid of 3 or 4 tiles, ONLY IF the document gives you enough to fill one \
honestly. The tiles are your verdict, not a lookup: the recommendation (one word -- \
"Pursue", "Pass", "Pursue with conditions"), the money, the fit against an agency that \
sells outcomes-led engagements, the clock. Use the document's own figures where it states \
them; where it does not, estimate, say what the estimate derives from, and signal it.

   OMIT THE GRID ENTIRELY when the document does not support one. A document that states \
no budget, no timeline and no criteria cannot fill a verdict row from anything but \
guesswork, and three tiles of guesswork presented as top-line facts is the worst thing \
you can put on this page. In that case let the callouts carry the whole read. Do NOT \
spend tiles on the client name, the sector or the reference number -- they are already on \
the page above you.

2. Callouts, one for each material thing the document establishes -- as many as it earns, \
and no more. The count follows the document, not a habit: work through the whole of it and \
cover what is actually there -- what is being asked for; how the process and the timeline \
run; the commercial position; what it requires of a respondent; who else is already \
involved. A document with several substantive numbered sections will earn several. A \
one-page enquiry will earn one or two, most of them risk-toned, because what matters \
about such a document is what it fails to say.

   Padding a thin document out to look substantial is a failure, and so is compressing a \
detailed one. Never return only one molecule.

   Give each one a `label` and a `source` when it is traceable to a numbered section. \
The tone carries the category:
     context         a fact or a quote drawn from the document.
     recommendation  what we should do about it. Sparing -- one, maybe two.
     risk            a gap, an unstated term, or an inference you are not confident in.

3. Add ONE score_table WHENEVER the document states evaluation criteria, weightings, or \
a scoring scheme. A document that publishes its weightings is asking to be scored, and \
describing those weightings in a paragraph instead is the wrong component. Use the \
document's own criteria and weights as its rows, and score each one as you honestly \
assess our position against it. If the document states no criteria at all, omit this \
family entirely.

4. ONE phase_plan WHENEVER the document sets out a process that runs in distinct \
stages -- a response deadline followed by shortlisting, presentations, award; a \
migration with milestones; a proof of concept before contract. Use the document's own \
stage names and its own dates, and put the timeframe in `when` exactly as it states it \
("Within 14 days", "By day 10", "Q4"). Two to four phases.

   A process described in a paragraph is a process drawn wrong -- if the document \
sequences events, the sequence is the component. OMIT THIS ENTIRELY when the document \
states no process, or states only a single deadline with nothing after it. An enquiry \
that says "no timeline has been agreed" gets no phase plan; it gets a risk band saying so.

5. ONE arc_beats -- three tiles labelled "Open", "Turn", "Close" -- WHEN the document \
tells you what this buyer is afraid of, what outcome it says it will measure, or what \
it has already decided. A document that states those things has handed you a position \
to take, and the arc is where that position goes; it is worth a molecule of the budget \
on a document like that. Each beat must trace to something the document states.

   OMIT IT when the document is thin. A one-page enquiry that has not decided its own \
budget, timeline or criteria does not support a pitch narrative, and inventing one from \
four paragraphs is exactly the guesswork this page exists to avoid.

THE SHAPE MUST FOLLOW THE DOCUMENT

A thin enquiry that states almost nothing should come back short and heavily flagged -- \
that is the correct answer, not a failure. A dense, highly specified document should come \
back long, with most of its bands sourced. Two different documents must not produce the \
same shape.

At most {schemas.MAX_MOLECULES} molecules in total. Fewer, denser molecules beat more \
thin ones, and padding to fill the budget is worse than either.

CAPABILITIES -- these are not optional, and a section with none of them is wrong

Every molecule carries `inspect` and `signal`. They are how a partner interrogates your \
work, so you must set them deliberately rather than leaving them off.

inspect = true on the metric_grid, and on every callout or table that carries a \
judgement, an estimate, or a claim traced to a section. In practice that is most of what \
you produce. Set it false only on a flat restatement with nothing to challenge.

signal = true where the document genuinely leaves you unable to answer and a human has \
to weigh in: a figure you estimated rather than read, a term the document declines to \
state, a material question it leaves open. Any tile or band whose content you inferred \
rather than found MUST be signalled -- presenting an estimate as though it were sourced \
is the one failure that actually costs the user money.

Signal what genuinely warrants it and no more. A section where everything is flagged has \
flagged nothing; a thin document may honestly warrant several, a complete one none.

DISCIPLINE

- Cite sections as the document numbers them ("§4", "§5(a)"). Never invent a section.
- Every figure is either stated in the document or clearly marked as your estimate. If \
the document states a budget, use it and do not flag it. If it does not and you estimate \
one, say what it is derived from and signal it.
- Quote the document's own language where it is doing work. The partner is going to be \
quoted back at.
- Write in the product's voice: short, declarative, no hedging, no "it appears that".
"""

INSPECT_PROMPT_BASE = """You are the Signal Review agent. The user has clicked one \
datapoint in the analysis and is asking about it -- where it came from, why it is \
flagged, or whether it is right.

Answer only from the document below. Quote the section that settles it. If the document \
does not settle it, say so plainly and say what would -- do not fill the gap with a \
plausible guess, because the user is deciding whether to trust the section.

You may attach at most two molecules when a component answers better than a sentence: \
an intel-card callout (tone context, with label and source) to show an attribution, or a \
metric_grid to lay out figures being compared. Attach nothing when prose is enough, \
which is most of the time.

Keep it to a few sentences.
"""


def section_prompt(document: Document) -> str:
    """The section agent's system prompt, for one document."""
    return f"{SECTION_PROMPT_BASE}\nTHE DOCUMENT\n{document.for_prompt()}\n"


def inspect_prompt(document: Document) -> str:
    """The review agent's system prompt, for one document."""
    return f"{INSPECT_PROMPT_BASE}\nTHE DOCUMENT\n{document.for_prompt()}\n"


class Event(NamedTuple):
    """One thing to push down the SSE connection.

    Three channels, and the split is deliberate. `a2ui` frames are real protocol
    messages and go straight to the client's `MessageProcessor` untouched.
    `meta` and `answer` are this application's own chrome -- the section
    subtitle, the signal count, the timings readout, the review pane's prose --
    which are not components and have no business inside a UI protocol.

    `trace` is the fifth, and the same kind of thing as `plan`: one molecule
    followed from the prompt to the pixels, for the walkthrough panel. Also
    diagnostic, also renders nothing.

    `plan` is the third: the model's structured output, sent verbatim so the
    protocol inspector can show what the agent returned next to what A2UI made
    of it. It is diagnostic only. **Nothing renders from it** -- the UI is drawn
    entirely from the `a2ui` channel, and that separation is the point of having
    the inspector at all.
    """

    kind: Literal["a2ui", "answer", "meta", "plan", "trace"]
    payload: dict


class Clock:
    """Monotonic stopwatch for the timings the demo reports on screen.

    Whether this approach lags was the open question behind the POC. The honest
    answer is a number, so every stream carries its own timings rather than
    leaving it to a feeling.

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


def _counts(molecules: list[Molecule]) -> dict[str, int]:
    """Running totals for the section head and the timings readout.

    The client cannot derive these itself any more: the molecules live in the
    A2UI surface's data model, which is owned by the renderer rather than by
    React state. Counting here keeps the chrome fed without asking the page to
    reach into the protocol's internals.
    """
    return {
        "molecule_count": len(molecules),
        "signal_count": sum(1 for molecule in molecules if molecule.signal),
    }


def _stream_section(document: Document, clock: Clock) -> Generator[Event, None, SectionPlan]:
    """Stream the model, pushing A2UI updates optimistically; return the plan.

    Returns:
        The completed, validated plan, for the caller's authoritative pass.

    Raises:
        ValueError: If the model refused, or returned nothing parseable.
    """
    optimistic: list[Molecule] = []

    with get_client().beta.chat.completions.stream(
        model=MODEL,
        messages=[{"role": "system", "content": section_prompt(document)}],
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
            for index in range(len(optimistic), len(raw) - 1):
                molecule = _parse_partial(raw[index])
                if molecule is None:
                    break
                optimistic.append(molecule)
                clock.mark_molecule()
                for message in a2ui.append_molecule(a2ui.SECTION_SURFACE_ID, optimistic):
                    yield Event("a2ui", message)
                yield Event("meta", _counts(optimistic))

        completion = stream.get_final_completion()

    choice = completion.choices[0]
    if choice.message.refusal:
        raise ValueError(f"model refused: {choice.message.refusal}")
    if choice.message.parsed is None:
        raise ValueError("model returned no parseable output")
    return choice.message.parsed


def _usable(molecules: list[Molecule]) -> list[tuple[Molecule, Molecule]]:
    """Sanitise a plan's molecules, dropping any that cannot be drawn.

    One unusable molecule does not sink the section -- a broken callout next to a
    good metric grid should cost the callout, not the answer.

    Returns:
        `(returned, drawn)` per surviving molecule, in render order. The pair is
        kept rather than just the sanitised molecule so the walkthrough can show
        what the sanitiser changed: once a molecule is dropped the two lists no
        longer share indices, and matching them back up afterwards would be a
        guess.
    """
    usable: list[tuple[Molecule, Molecule]] = []
    for molecule in molecules[: schemas.MAX_MOLECULES]:
        try:
            usable.append((molecule, _sanitize(molecule)))
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

    The fallback is itself a molecule -- a risk-toned callout, compiled through
    the same A2UI path as everything else -- rather than a special-cased error
    shape. If the renderer can draw the failure state, the renderer is the only
    thing that ever draws.

    It replaces rather than creates: `run_overview` opens the surface before it
    can fail, so by the time this runs the surface always exists, and a second
    `createSurface` for the same id is not something to make the client reason
    about.
    """
    lead, body = FALLBACK_COPY[error]
    notice = schemas.Callout(tone="risk", lead=lead, body=body)
    for message in a2ui.replace_surface(a2ui.SECTION_SURFACE_ID, [notice]):
        yield Event("a2ui", message)
    yield Event(
        "meta",
        {
            "ok": False,
            "error": error,
            "summary": "This section could not be generated.",
            "total_ms": clock.elapsed_ms(),
            "first_molecule_ms": clock.first_molecule_ms,
            **_counts([notice]),
        },
    )


def run_overview(document: Document) -> Iterator[Event]:
    """Stream the analysis of one document. Never raises: every path yields a surface."""
    clock = Clock()

    # Opened before anything that can fail, so every path below -- success,
    # refusal, missing key, dead network -- has a surface to write into and only
    # ever needs to replace its contents.
    for message in a2ui.open_surface(a2ui.SECTION_SURFACE_ID):
        yield Event("a2ui", message)

    if not os.getenv("OPENAI_API_KEY"):
        yield from _fallback("missing_api_key", clock)
        return

    try:
        plan = yield from _stream_section(document, clock)
    except ValidationError as exc:
        logger.warning("agent output failed validation: %s", exc)
        yield from _fallback("schema_validation_failed", clock)
        return
    except Exception:  # network, auth, rate limit, refusal, anything upstream
        logger.exception("overview generation failed")
        yield from _fallback("upstream_error", clock)
        return

    # The model's own output, before this module touches it. Sent for the
    # inspector, and taken before `_usable` on purpose: comparing `returned`
    # against `rendered` is how a dropped molecule becomes visible in a demo
    # rather than a silent absence.
    yield Event(
        "plan",
        {
            "model": MODEL,
            "summary": plan.summary,
            "molecules": [molecule.model_dump(mode="json") for molecule in plan.molecules],
        },
    )

    pairs = _usable(plan.molecules)
    if not pairs:
        yield from _fallback("unusable_molecules", clock)
        return
    final = [drawn for _, drawn in pairs]

    # The authoritative pass. Replace-wins is load-bearing: this overwrites
    # anything the optimistic pass parsed out of half-written JSON.
    for message in a2ui.replace_surface(a2ui.SECTION_SURFACE_ID, final):
        yield Event("a2ui", message)

    # One molecule, followed from the prompt to the pixels, for the walkthrough
    # panel. Built from this run rather than written out, so it explains what the
    # system does instead of what it was once documented to do. Its own surface
    # is opened here, on the same channel as everything else.
    traced = walkthrough.choose(final)
    returned, drawn = pairs[traced]
    trace = walkthrough.build(
        instructions=SECTION_PROMPT_BASE,
        document_text=document.for_prompt(),
        model=MODEL,
        returned=returned,
        drawn=drawn,
        index=traced,
    )
    for message in trace.pop("a2ui"):
        yield Event("a2ui", message)
    yield Event("trace", trace)

    yield Event(
        "meta",
        {
            "ok": True,
            "error": None,
            "summary": plan.summary,
            "total_ms": clock.elapsed_ms(),
            "first_molecule_ms": clock.first_molecule_ms,
            # What the compiler wrote on the model's behalf for *this* document,
            # for the panel that weighs compiling against emitting A2UI directly.
            "directness": a2ui.directness_cost(final),
            **_counts(final),
        },
    )


def run_inspect(
    document: Document, question: str, subject: str, history: list[Turn]
) -> Iterator[Event]:
    """Answer a review-pane question about one inspected molecule.

    Args:
        document: The document under analysis, so the answer is grounded in the
            same text the section was drawn from.
        question: What the user typed.
        subject: A short description of the molecule they clicked, so the model
            knows what "this" refers to without the client resending the tree.
        history: Prior turns in this review conversation.

    Yields:
        A2UI frames for any attached molecules, then one `answer` event, then
        `meta`. Never raises.
    """
    clock = Clock()

    if not os.getenv("OPENAI_API_KEY"):
        _, body = FALLBACK_COPY["missing_api_key"]
        yield Event("answer", {"answer": body, "surface_id": None})
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
                {"role": "system", "content": inspect_prompt(document)},
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
        yield Event("answer", {"answer": body, "surface_id": None})
        yield Event(
            "meta",
            {"ok": False, "error": "upstream_error", "total_ms": clock.elapsed_ms()},
        )
        return

    # Attached molecules go on their own surface, sent before the answer that
    # references it, so the pane never renders a turn pointing at a surface the
    # processor has not seen yet.
    attached = [drawn for _, drawn in _usable(parsed.molecules)]
    surface_id = f"{a2ui.INSPECT_SURFACE_PREFIX}{uuid4().hex[:8]}" if attached else None
    if surface_id:
        for message in a2ui.full_surface(surface_id, attached):
            yield Event("a2ui", message)

    yield Event("answer", {"answer": parsed.answer, "surface_id": surface_id})
    yield Event("meta", {"ok": True, "error": None, "total_ms": clock.elapsed_ms()})
