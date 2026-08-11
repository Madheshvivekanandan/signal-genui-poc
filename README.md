# Signal · Generative UI POC

Agent output rendered as Signal design-system molecules, streamed as they are decided.

This is the POC Harman asked for in the 2026-08-11 review: take the Signal design system's
components, have an agent choose among them based on what it reads, and find out whether it
lags. It is deliberately **not** a chat interface that draws charts — the model never writes
markup, never picks a colour, and never decides the page structure.

## What is generated and what is not

| | Owner |
|---|---|
| Page shell — nav, RFP header, numbered accordion, locked sections, CTA | **Hand-built.** Static. |
| Which molecule family a statement becomes | **Agent.** |
| How many instances, and their content | **Agent.** |
| Variant — callout tone, score band | **Agent**, as a *meaning* (`risk`, not `.alert`). |
| `inspect` / `signal` capability flags | **Agent.** |
| Markup, class names, colours, grids, type scale | **Design system.** `signal.css`, untouched. |

The agent's entire vocabulary is the `Molecule` union in `backend/schemas.py`. Anything outside
it fails validation and never reaches the browser.

## The three molecule families

Implemented from the design system's §3, chosen because together they are the whole visible
surface of the RFP Overview screen:

- **`metric_grid`** — DS §3.1. Top-line facts, 3 or 4 tiles.
- **`callout`** — DS §3.2. The banded component: one component, three line colours
  (navy = context, teal = recommendation, coral = risk), optional intel header with source.
- **`score_table`** — DS §3.3. Score rows with an aligned total.

Adding a fourth is exactly two edits: a Pydantic model added to the union in
`backend/schemas.py`, and an entry in `frontend/src/molecules/registry.jsx`.

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
| GET | `/api/health` | liveness, model, whether a key is set |
| GET | `/api/rfp` | the static header facts — *not* generated |
| GET | `/api/sections/rfp-overview` | SSE: the section, streamed |
| POST | `/api/inspect` | SSE: an answer about one inspected molecule |

## Measured performance

Harman asked twice whether this lags, so the numbers are on screen (`Timings.jsx`) rather than
asserted. Observed across runs on `gpt-4o-mini`:

| | |
|---|---|
| First component painted | **2.4 – 7.3 s** |
| Section complete | **5.5 – 10.6 s** |
| Wait avoided by streaming | **~3.0 – 3.2 s** |
| Inspect-pane answer | **~2 s** |

The gap between first paint and section-complete is what streaming buys: roughly half the wait
is removed, because the metric grid is interactive while the model is still writing the last
callout. Molecules arrive ~0.6–0.8 s apart.

**Caveat: these are one machine, one model, one document, single-digit runs.** They are
directional, not a benchmark. `gpt-4o-mini` is also the weakest sensible model here — a larger
model will be slower per token and better at the judgement calls, and that trade has not been
measured.

## How the streaming works

The generation is streamed **twice over**, which is what makes the interface build rather than
arrive:

1. **Optimistically**, from the model's partially-parsed JSON. A molecule is emitted the moment
   it is provably finished — meaning the next one has started — so the grid paints while the
   third callout is still being written.
2. **Authoritatively**, once the stream closes. The completed object is validated and sanitised,
   and the whole section is re-sent as a replace. Anything the first pass got wrong or skipped is
   corrected before the user can act on it.

Replace-wins is load-bearing. Do not merge the two writers.

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
| Coercers + whitelist dispatch | wrong types, nulls, unknown or prototype-polluting `type` |
| `<ErrorBoundary>` per molecule | any render-time throw |

Backend failures arrive as a **renderable molecule** — a risk-toned callout — not as a special
error shape. If the renderer can draw the failure state, the renderer is the only thing that
ever draws. No raw exception text, stack, or upstream message is ever shown to the user.

## Findings worth reporting back

Things this exercise turned up, beyond "it works":

1. **A2UI was not used, and this use case does not need it.** Harman's scepticism about v0.9
   was well placed. With a fixed design system, a closed component set and server-owned data,
   A2UI's binding layer solves a problem this product does not have. The wire format here is
   plain JSON over SSE, and the seam (`agent` → typed molecules → `registry.jsx`) is thin enough
   that A2UI or Vercel's json-renderer could be dropped in behind it for a like-for-like
   comparison against Kunal's track. A versioned in-house contract is the likely production
   answer.
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
- **`score_table` is implemented but rarely chosen**, because this RFP declines to state
  evaluation weightings. It needs a document that scores to be exercised properly.
- **No tests.** The highest-value targets are `registry.jsx` against malformed and hostile
  payloads, and `stream.js` frame-splitting across chunk boundaries.
- The wallpaper is a gradient stand-in; the DS export references
  `signal background clean.jpg`, which is not in the HTML file.

## Gates

```bash
cd frontend && npm run lint    # oxlint src — clean
cd frontend && npm run build   # 203 kB / 64 kB gzipped, 55 kB CSS
```

There is no TypeScript and no test framework in this project. `npm run build` succeeding means
it compiled, not that it works — run the app.

## Layout

```
backend/
  schemas.py        # the agent's entire vocabulary — read this first
  agent.py          # streaming, the two passes, prompts, fallbacks
  main.py           # thin routes + SSE framing
  rfp_document.py   # the input, as a fixture
frontend/src/
  signal.css        # VENDORED design system — do not edit
  app.css           # only what the DS does not define
  molecules/
    registry.jsx    # the whitelist dispatch — read this second
    MetricGrid.jsx  Callout.jsx  ScoreTable.jsx  InspectTarget.jsx
  shell/            # static chrome: Header, Section, ReviewPane, Timings
  lib/              # stream.js (the whole backend contract), coerce.js
```

`.claude/skills/` carries the Python and React standards this repo is written to.
