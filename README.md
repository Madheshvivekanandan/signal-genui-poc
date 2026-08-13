# Signal · Generative UI POC

Agent output rendered as Signal design-system molecules over **A2UI v0.9**, streamed as they
are decided.

The brief: take the Signal design system's components, have an agent choose among them based
on what it reads, and find out whether it lags. It is deliberately **not** a chat interface that draws charts — the model never writes
markup, never picks a colour, and never decides the page structure.

The transport and the renderer are A2UI, Google's protocol for agent-generated UI. The agent
plans in typed molecules; `backend/a2ui.py` compiles those into real `createSurface` /
`updateDataModel` / `updateComponents` messages, and `@a2ui/react` draws them against the
closed catalog in `frontend/src/a2ui/catalog.jsx`. No rendering code of ours sits between a
protocol message and the DOM.

## What is generated and what is not

| | Owner |
|---|---|
| Page shell — nav, RFP header, numbered accordion, locked sections, CTA | **Hand-built.** Static. |
| Which molecule family a statement becomes | **Agent.** |
| How many instances, and their content | **Agent.** |
| Variant — callout tone, score band | **Agent**, as a *meaning* (`risk`, not `.alert`). |
| `inspect` / `signal` capability flags | **Agent.** |
| Markup, class names, colours, grids, type scale | **Design system.** `signal.css`, untouched. |
| Component names, layout, data binding | **A2UI.** Compiled by `backend/a2ui.py`. |

The agent's entire vocabulary is the `Molecule` union in `backend/schemas.py`. Anything outside
it fails validation and never reaches the browser.

Note what the agent does *not* do: it never names an A2UI component and never writes a
binding. It returns molecules; the compiler decides that a `callout` is a `Callout` bound to
`/molecules/1/*`. So there are two closed sets, not one — the molecule union the model
generates against, and the catalog the renderer will accept.

## The five molecule families

The first three are the whole visible surface of the RFP Overview screen. The last two come
from §3.4, which the design system places on the Framing and Generation screens — carried here
deliberately, so a document that sets out a process reads differently from one that does not:

- **`metric_grid`** — DS §3.1. Top-line facts, 3 or 4 tiles.
- **`callout`** — DS §3.2. The banded component: one component, three line colours
  (navy = context, teal = recommendation, coral = risk), optional intel header with source.
- **`score_table`** — DS §3.3. Score rows with an aligned total.
- **`phase_plan`** — DS §3.4. Navy-banded phase cards: tag, name, the timeframe in the
  document's own words, dot-bulleted scope. 2–4 phases in one molecule.
- **`arc_beats`** — DS §3.4. The three-up story arc on inner surfaces. Fixed at three,
  because `.arc-beats` is `repeat(3, 1fr)` and two would leave an empty column.

§3.4's third component, the **case card**, is deliberately absent. It renders our own past work
— a rank, an outcome figure, a positioning line — none of which appears in an opportunity
document, so the model could only invent it.

Adding a sixth is exactly three edits, and they must stay in step: a Pydantic model added to
the union in `backend/schemas.py`, a row in `_VIEW` in `backend/a2ui.py` naming the component
and the fields it binds, and a component registered in `frontend/src/a2ui/catalog.jsx`. (It was
two before A2UI; the compiler is the third.) In practice a family also wants a rule in
`SECTION_PROMPT_BASE` saying when it is earned — without one the model will not reach for it.

### What the agent actually picks

Observed on `gpt-4o`, three runs across all four fixtures:

| | metric_grid | callout | score_table | phase_plan | arc_beats |
|---|---|---|---|---|---|
| Cedar | ✓ | 3–4 | sometimes | ✓ | — |
| Meridian | ✓ | 1–4 | ✓ | ✓ | — |
| Halcyon | ✓ | 3 | — | ✓ | — |
| Northwind | — | 4, mostly risk | — | — | — |

`phase_plan` is picked by every document that sequences events and correctly omitted by
Northwind, which states "no timeline has been agreed". **`arc_beats` was never chosen** — not
in twelve generations, and not when promoted to third in the prompt. The molecule budget was
not the constraint; runs that left a slot free still skipped it. The honest reading is that
against a procurement document the model does not judge a pitch narrative to be earned, which
is the behaviour the prompt asks for. It stays in the catalog: a closed vocabulary the agent
declines part of is the claim working, not failing.

## A2UI

The wire format is A2UI v0.9 — not v1.0. As of August 2026 v0.9.1 is still the current stable
spec and v1.0 remains a Candidate, and `@a2ui/react` ships `v0_8` and `v0_9` entry points with
no v1.0 one, so v0.9 is the only version that renders natively today.

What A2UI actually contributes here:

- **Four server-to-client messages.** `createSurface` opens the section body; `updateDataModel`
  writes values; `updateComponents` adds or replaces components by id; `deleteSurface` closes a
  surface. The client builds only the last one, on pane close.
- **A binding layer.** Components carry `{"path": "/molecules/0/body"}` rather than inline
  values, so the data model and the component tree are updated independently.
- **A catalog as the security boundary.** A component name the agent invents is rejected by the
  renderer before it reaches any code of ours — a stronger version of the whitelist dispatch
  this POC used previously, because it is enforced by the library rather than by a check we
  have to remember to write.
- **An action channel.** Clicking an inspect target dispatches a real A2UI action
  (`{event: {name: "inspect", context: {subject}}}`), which arrives at the `MessageProcessor`'s
  handler. It is not a React callback threaded through props.

The catalog is six components: `MoleculeStack`, `MetricGrid`, `Callout`, `ScoreTable`,
`PhasePlan`, `ArcBeats`.
**A2UI's basic catalog is deliberately not registered.** `Column`, `Row` and `Card` inject
their own flex styles and spacing variables, which would compete with `signal.css` for control
of the section body; `MoleculeStack` draws the DS's own `.molecule-stack` and nothing else. A
consequence worth knowing: none of A2UI's stylesheets are imported, so there is no cascade to
reconcile.

`CATALOG_ID` must match on both sides. It is an identifier, never fetched. `/api/health`
reports the protocol and catalog for exactly this reason — a browser holding a stale catalog is
otherwise indistinguishable from an agent producing nothing.

**`zod` must stay on v3.** The binder classifies props by reading Zod 3 internals
(`_def.typeName`). Zod 4 renamed those and the failure mode is silent: every prop degrades to
`STATIC` and bindings render as `[object Object]`.

## Running it

Two processes. Backend first.

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env          # gitignored
.venv/bin/uvicorn main:app --port 8000

# Frontend (separate shell)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

If port 8000 is taken, run the backend elsewhere and point the dev proxy at it:

```bash
.venv/bin/uvicorn main:app --port 8123
BACKEND_URL=http://127.0.0.1:8123 npm run dev
```

Or the whole thing under Docker, which proxies `/api` through nginx so the browser only makes
same-origin requests:

```bash
cp .env.example .env    # add your key
docker compose up --build   # http://localhost:3000
```

### Endpoints

| Method | Path | |
|---|---|---|
| GET | `/api/health` | liveness, model, key presence, protocol, catalog id |
| GET | `/api/documents` | the documents this build can analyse, and the default |
| GET | `/api/catalog` | the molecule vocabulary, introspected from `schemas.py`, plus specimens |
| GET | `/api/rfp?document=` | the static header facts — *not* generated |
| GET | `/api/sections/rfp-overview` | SSE: A2UI messages for the section, streamed |
| POST | `/api/inspect` | SSE: an answer, plus A2UI messages for anything it attaches |

Three SSE channels share both streams, told apart by the `event:` name:

| `event:` | |
|---|---|
| `a2ui` | a real A2UI v0.9 message, handed to the `MessageProcessor` verbatim |
| `meta` | this app's chrome — section subtitle, signal count, timings. Not A2UI. |
| `answer` | the review pane's prose, plus the id of any surface it attached |
| `plan` | the model's raw structured output, for the protocol inspector. Renders nothing. |

Keeping chrome out of the `a2ui` channel is deliberate. The section subtitle and the timings
readout are not components and modelling them as such would mean the agent could change them.

## Four documents, four compositions

The POC's claim is that one catalog and one renderer produce different interfaces for
different documents. One fixed document cannot demonstrate that, so `backend/documents.py`
carries four, shaped to demand different answers to "which components does this deserve?".
Pick one from the strip above section 1 and the section re-composes.

| Document | What it states | What the agent composed |
|---|---|---|
| **Cedar Wellness** | Rich, but no budget and no weightings | grid + 3 context + **1 coral risk** · 2 signals |
| **Meridian Health** | Published weightings *and* a real budget | grid + 3 context + **scored table** · 0 signals |
| **Northwind** | Almost nothing — an RFI, not an RFP | **no grid at all**, risk-led · 3 signals |
| **Halcyon Bank** | Dense, highly specified, fully costed | grid + 4 context · 0 signals |

Two of these are structurally unmistakable. **Northwind produces no metric grid**, because a
document stating no budget, no timeline and no criteria cannot fill a verdict row from
anything but guesswork — the agent decides that, it is not special-cased. **Meridian
produces a score table** carrying the document's own published weightings, because it is
the only one that publishes any.

Cedar and Halcyon compose similarly, and that is the honest result rather than a gap: both
are dense, complete RFPs that state their budget and their deadline, so they earn the same
components. Say that out loud before switching to Northwind and the difference reads as
evidence. With three molecule families the space of possible shapes is genuinely
small — widening it means a fourth family, which the review capped at two or three.

**Run demos on `gpt-4o`, not `gpt-4o-mini`.** Mini intermittently returns a single molecule
and stops — `finish_reason=stop`, no refusal, roughly one run in four, on more than one
document. `gpt-4o` did not do it across 8+ runs and is *faster* here (3.4–4.4 s vs
5–14 s). Set `OPENAI_MODEL=gpt-4o`.

The prompt earns its own note. It was originally written for the Cedar document and carried
instructions *about* that document — "this one does not give you weightings, so you almost
certainly should not [use a score_table]" — which travelled to every other document and
suppressed a whole molecule family. **An agent that analyses documents cannot hold opinions
about one.** The base prompt is now document-agnostic and the document is appended per
request.

## The protocol inspector — for demoing this

Collapsed at the bottom of the page. Open it and it shows, in order:

1. **Agent output** — the model's structured JSON exactly as it came back. Nothing in it names
   a component, a class or a colour.
2. **The compile** — each molecule mapped to the A2UI component it became and the data-model
   paths it binds. `callout [1]` → `Callout id=m1` → `body → /molecules/1/body`. This is the step
   people assume is magic.
3. **The stream** — every frame in arrival order, channel-tagged, with relative timings and the
   raw JSON one click away. The `A2UI` chips are the only frames that draw anything.
4. **Measured** — what the three stages above cost in wall-clock time. It lives here rather than
   on the page: instrumentation belongs with instrumentation.

The fifth stage is the page above it. **Nothing renders from stages 1–4** — delete the inspector
and the UI is byte-identical, which is the property being demonstrated: the model produced data,
and the protocol produced the interface.

## The catalog offered to the agent

At the foot of the page, kept separate from everything above it: every component the model may
choose from, and nothing else. The claim this POC rests on is that the vocabulary is closed, and
that is only checkable if the vocabulary is visible.

Each family arrives twice over, because a name does not tell you what a `callout` is:

- **The specimen.** A real molecule, compiled by `a2ui.py` and drawn by `A2uiSurface` against the
  same catalog that renders the section above — the same path, the same components. It is not a
  picture of the component; it is the component. The specimen content describes the field it
  occupies, so the band explains what a band is for.
- **The field table.** Every field the model may set, its type, its closed set of allowed values,
  its length bounds, and the `Field(description=…)` prose. That description is not a gloss written
  for this page — Pydantic puts it in the JSON Schema and the JSON Schema *is* the
  `response_format`, so it is literally what the model reads.

Both come from `/api/catalog`, which introspects `schemas.py` rather than restating it. Change a
bound or a tone in the schema and the panel reports the new one; there is no second copy to keep
in step.

Specimens carry `inspect: false` — the flag is documented in the table, but a gallery band that
opened the review pane would send the model a question about a specimen.

A demo script that lands in about ninety seconds:

1. Reload with the inspector closed. Watch the section build — grid first, then bands. That is
   the streaming claim, visible.
2. Scroll to the catalog at the foot of the page: *"this is everything it may return."* Three
   components and their fields — then scroll back and switch documents to watch the same three
   produce a different shape.
3. Open the inspector. Stage 1: *"this is all the model returned — it's data, there is no UI in
   it."*
4. Stage 2: *"this is where it became UI, and no model chose any of it."* Point at one binding.
5. Stage 3: scroll to the last `updateComponents`. It lists every component at once — the
   authoritative pass replacing the optimistic one. Compare it to the earlier single-component
   frames.
6. Stage 4: first component vs. section complete. The gap is what streaming bought.
7. Click the budget tile. The pane opens from a real A2UI action, and the agent declines to
   defend the estimate.

The `plan` channel exists only for this. It carries the model's output *before* `_usable()`
drops anything, so a dropped molecule shows up as a red note in stage 2 rather than as a silent
absence — worth knowing, because that difference is a good demo moment when it happens.

## Measured performance

Whether this lags was the open question behind the POC, so the numbers are on screen
(`Timings.jsx`, as the inspector's stage 4) rather than asserted. Observed across runs on
`gpt-4o-mini`:

| | On A2UI | Before A2UI |
|---|---|---|
| First component painted | **2.6 – 8.7 s** | 2.4 – 7.3 s |
| Section complete | **4.6 – 10.6 s** | 5.5 – 10.6 s |
| Wait avoided by streaming | **1.9 – 3.3 s** | ~3.0 – 3.2 s |
| Inspect-pane answer | **~2.4 s** | ~2 s |

The gap between first paint and section-complete is what streaming buys: roughly half the wait
is removed, because the metric grid is interactive while the model is still writing the last
callout.

**A2UI did not measurably change these numbers.** That is the expected result rather than a
happy one: the wait is dominated by token generation, and the protocol only decides how the
bytes are framed once the model has produced them. The run-to-run spread within either column
is wider than any difference between the columns, so this comparison can rule out a large
regression and nothing finer.

Where A2UI does cost something is the bundle:

| | Before | On A2UI |
|---|---|---|
| JS | 203 kB / 64 kB gzipped | **371 kB / 108 kB gzipped** |
| Modules | 29 | **413** |
| Runtime deps | 2 | **5** |

+44 kB gzipped and 384 modules, for a renderer and a binding layer. On a first visit that is
real; against a 2.6–8.7 s wait for the first component, it is not what the user is waiting for.

**Caveat: these are one machine, one model, one document, single-digit runs.** They are
directional, not a benchmark.

The `gpt-4o-mini` numbers above are the original measurement. On `gpt-4o` the section
completes in **3.4–4.4 s** — *faster*, not slower, which was not the expected result and
suggests these timings are dominated by something other than per-token cost at this
document size. It is also the model demos should use, for the reliability reason in
"Four documents, four compositions".

## How the streaming works

The generation is streamed **twice over**, which is what makes the interface build rather than
arrive:

1. **Optimistically**, from the model's partially-parsed JSON. A molecule is compiled the moment
   it is provably finished — meaning the next one has started — and sent as an
   `updateDataModel` plus an `updateComponents` carrying only the new component and the root, so
   the grid paints while the third callout is still being written. Bands already on screen are
   addressed by id and do not repaint.
2. **Authoritatively**, once the stream closes. The completed object is validated and sanitised,
   and the whole surface is re-sent — the full data model and every component. Anything the first
   pass got wrong or skipped is corrected before the user can act on it.

Replace-wins is load-bearing. Both passes emit the same message types; what differs is the
source of truth — half-written JSON versus a validated plan. Do not collapse the two callers.

A worked example from a real run: the optimistic pass sent `m0`…`m3` one at a time, then the
authoritative pass sent `m0,m1,m2,m3,m4,root` in one message — the fifth molecule had never
been emitted optimistically, and appeared only because the second pass replaced everything.

Data is always sent before the components that bind to it, so no binding is ever live against a
model that does not yet hold its value.

Buffering is the one thing that silently kills this: the backend sends
`X-Accel-Buffering: no`, and `frontend/nginx.conf` sets `proxy_buffering off`. With either
missing, every frame is held until the turn ends and the progressive render becomes one late
repaint — i.e. it looks exactly like the thing this POC exists to disprove.

## Error handling

Five layers, each catching what the others cannot. The design goal is that the page cannot be
made to crash by model output.

| Layer | Catches |
|---|---|
| Structured outputs | invented molecule types, missing fields |
| `_sanitize()` | valid shape, unusable content (orphan source, headerless band) |
| SSE frame parsing | malformed frame, non-JSON payload |
| A2UI catalog validation | unknown component name, malformed component definition |
| Coercers in the molecules | wrong types, nulls, a number where a string belongs |
| `<ErrorBoundary>` per molecule | any render-time throw |

Six layers now, not five: A2UI's catalog validation replaced the registry's `hasOwnProperty`
dispatch, and it is a stronger boundary because the library enforces it rather than a check of
ours. The prototype-pollution concern the old dispatch guarded against no longer applies —
component names are matched against a catalog map, never used to index an object.

Every molecule is still individually wrapped in `<ErrorBoundary>`, inside the catalog
implementation. One malformed band must cost its own band and not the section.

Backend failures arrive as a **renderable molecule** — a risk-toned callout compiled through the
same A2UI path as everything else — not as a special error shape. If the renderer can draw the
failure state, the renderer is the only thing that ever draws. No raw exception text, stack, or
upstream message is ever shown to the user. The one failure the backend cannot report is a dead
connection, and the client builds those A2UI messages itself
(`frontend/src/a2ui/messages.js`).

## Findings worth reporting back

Things this exercise turned up, beyond "it works":

1. **A2UI works for this use case, and the swap was small.** This build previously used a plain
   in-house JSON contract and argued A2UI's binding layer solved a problem the product does not
   have. It now runs on A2UI v0.9, and the honest report is mixed:

   - **The migration was cheap** — one new backend module, one new frontend catalog, and the
     three molecule components were reused untouched. The thin seam the earlier design left
     (`agent` → typed molecules → renderer) is what made it cheap, and that seam is worth
     keeping whatever the wire format ends up being.
   - **The design system survived intact.** `signal.css` is still unedited and the rendered page
     is pixel-identical, but only because A2UI's basic catalog was left unregistered. Adopting
     `Column`/`Row`/`Card` would have put A2UI's spacing model in competition with the DS's.
     Anyone adopting A2UI over an existing design system should expect to make that same call.
   - **The binding layer is still not load-bearing here.** Data and structure *can* be updated
     independently, and this app has no case that needs it: every update replaces content
     wholesale. The value delivered is the renderer, the catalog boundary and the action
     channel — not the bindings.
   - **The maturity objection has not resolved.** v0.9.1 is still the stable spec and v1.0 is
     still a Candidate, eight months after it was first raised. `@a2ui/react` has no v1.0 entry
     point. Anything built on v0.9 today should expect a migration.
   - **Cost:** +44 kB gzipped, 3 new runtime dependencies, and a hard constraint on `zod@^3`
     because the binder reads Zod 3 internals.

   The earlier recommendation — a versioned in-house contract — is not refuted by this, and the
   two options are now genuinely comparable because both have been built.
2. **Two token bugs in the design system export.** `--caution` and `--navy-hover` are declared
   self-referentially (`--caution: var(--caution)`), which is invalid CSS — the declaration is
   dropped, so amber utilization bars and navy button hovers are unstyled in the DS page itself.
   Fixed here with the values §1.1 documents; the export needs the same fix.
3. **The DS's inspect affordance is keyboard-inaccessible as authored.** All 21 inspect targets
   in the export are `<div>`s with no role and no tab stop, and the stylesheet has no button
   reset — so wrapping them in a `<button>` visibly breaks the band. `InspectTarget.jsx` adds
   the semantics without changing the markup, but the real fix belongs in the design system.
4. **§3.2 says "no separate intel card component"; the CSS still ships two.** `.callout` and
   `.intel-card` are distinct classes with different line colours and radii. One React component
   reconciles them here, per the annotation's stated intent.
5. **Structured outputs rejects discriminated unions.** Pydantic emits `oneOf` for
   `Field(discriminator=...)`, and the API returns a 400. A plain union (`anyOf`) is required —
   noted in `schemas.py` so it does not get "improved" back.
6. **Prompting drives capability flags more than anything else.** The first version returned
   every molecule with `inspect=false, signal=false`, so nothing was clickable and no coral band
   appeared — the page rendered but the product didn't work. It also spent metric tiles
   restating the header. Both were fixed in the prompt, not the code.

### Known gaps

- **The agent does not reliably signal the budget *tile*.** It signals the budget *callout*
  instead. The estimate is the clearest case of an inferred figure and the prompt says so
  explicitly; `gpt-4o-mini` still misses it about half the time. Worth retrying on a stronger
  model before treating it as a prompt problem.
- **Only one agent and one section.** Sections 2 and 3 are locked chrome. Nothing here proves
  the pattern across agents with different output shapes — that is the next thing to test.
- ~~`score_table` is never chosen~~ — **fixed.** It renders for Meridian, carrying that
  document's own published weightings. The cause was never the family: the prompt held a
  Cedar-specific instruction not to use it. Its binding path was also verified directly
  against `MessageProcessor` — `total` binds to a plain object, which `DynamicValue` has no
  member for, and it resolves because the binder classifies props rather than validating
  resolved values.
- **Only two of the four documents are structurally unmistakable.** Northwind (no grid) and
  Meridian (score table) are; Cedar and Halcyon compose alike because they are both dense,
  complete RFPs. Defensible, but with three families the shape space is small — a fourth
  family is the real lever, and the review capped it at two or three.
- **No tests.** The highest-value targets are now `a2ui.py`'s compiler output, the catalog's
  binding resolution, and `stream.js` frame-splitting across chunk boundaries.
- The wallpaper is a gradient stand-in; the DS export references
  `signal background clean.jpg`, which is not in the HTML file.

## Gates

```bash
cd frontend && npm run lint    # oxlint src — clean
cd frontend && npm run build   # 371 kB / 108 kB gzipped, 55 kB CSS
```

There is no TypeScript and no test framework in this project. `npm run build` succeeding means
it compiled, not that it works — run the app.

## Layout

```
backend/
  schemas.py        # the agent's entire vocabulary — read this first
  a2ui.py           # A2UI v0.9 builders + the molecule -> A2UI compiler — read this second
  agent.py          # streaming, the two passes, prompts, fallbacks
  main.py           # thin routes + SSE framing
  documents.py      # the four input documents, as fixtures
frontend/src/
  signal.css        # VENDORED design system — do not edit
  app.css           # only what the DS does not define
  a2ui/
    catalog.jsx     # the six components an agent may put on screen — read this third
    messages.js     # the two messages the client builds for itself
  molecules/        # the DS implementations, unchanged by the A2UI migration
    MetricGrid.jsx  Callout.jsx  ScoreTable.jsx  InspectTarget.jsx
  shell/            # static chrome: Header, Section, ReviewPane
                    # + DocumentPicker, MoleculeCatalog, ProtocolInspector
                    #   (Timings renders inside it) — demo surfaces
  lib/              # stream.js (the SSE contract), coerce.js
```

`.claude/skills/` carries the Python and React standards this repo is written to.
