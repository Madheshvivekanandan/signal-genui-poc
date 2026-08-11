---
name: react-best-practices
description: React standard for the signal-genui-poc frontend — a Vite + React 19 SPA (plain JSX, no TypeScript) that renders a fixed Signal design-system page whose section bodies are composed by an agent from a closed molecule catalog. Load BEFORE writing, modifying, or reviewing any frontend code in this repo — anything under frontend/src/ (App.jsx, molecules/, shell/, lib/) or any .jsx/.css file. Covers the vendored design system, the molecule registry contract, defensive rendering, error boundaries, state, a11y, performance, and a review checklist.
---

# React Best Practices — signal-genui-poc frontend

Correctness and clarity first, then performance. Adapted from React docs, Vercel
Engineering's react-best-practices (MIT), and WCAG, cut down to what this app is.
**When this document conflicts with the existing code, follow the code and say so.**

## 0. This project — the actual stack

```
frontend/src/
  main.jsx                 # entry; imports signal.css THEN app.css
  App.jsx                  # page state, the two stream writers, inspect state
  signal.css               # VENDORED design system — treat as read-only
  app.css                  # POC-only styles the DS does not define
  lib/
    stream.js              # the ENTIRE backend contract — the only place fetch appears
    coerce.js              # untrusted-payload coercers + capability classes
  molecules/
    registry.jsx           # the whitelist dispatch — the heart of the app
    MetricGrid.jsx  Callout.jsx  ScoreTable.jsx  InspectTarget.jsx
  shell/
    Header.jsx  Section.jsx  ReviewPane.jsx  Timings.jsx
  components/
    ErrorBoundary.jsx
```

- **Vite + React 19, plain JSX. There is no TypeScript**, no `tsc`, no type-checking gate.
- **Zero runtime dependencies beyond react + react-dom.** No charting library, no router,
  no state library, no data-fetching library.
- **Plain CSS.** `signal.css` is lifted from the Signal DS HTML export; `app.css` holds only
  what the DS lacks.

**Rules that do not apply here — never suggest them:** RSC / `"use client"`, anything
`next/*`, SSR/hydration, MUI, Tailwind, Recharts or any chart palette rule, `useSearchParams`
(there is no router).

## 1. The vendored design system

`signal.css` is **not ours to edit.** It is the first `<style>` block of
`2026-07-19_Signal_DS_v23_Foundations_UI_Library_v2.html`, kept diffable so a newer export can
be dropped over the top.

- **Never restyle a DS class in `signal.css`.** New rules go in `app.css`, which loads second.
- **Three deviations exist and are marked `POC:`** — the wallpaper (a missing binary) and two
  self-referential token bugs (`--caution`, `--navy-hover`). Do not add a fourth without marking it.
- **Do not invent DS class names.** If a class is not in `signal.css`, either it belongs in
  `app.css` as POC scaffolding, or the design system needs to define it — say which.
- **The row grids are the spec.** DS §3.3 says so explicitly. Never set a column width on a
  `.score-row`; it comes from the stylesheet.
- **DS inspect targets are `<div>`s and the stylesheet has no button reset.** Wrapping a band in
  a `<button>` inherits UA styling and visibly breaks it. Use `InspectTarget`, which adds
  `role="button"` + `tabIndex` + Enter/Space handling and keeps the markup as the DS ships it.

## 2. The molecule registry contract

The backend sends `{type, ...props}` drawn from a closed Pydantic union. `molecules/registry.jsx`
turns that into DOM. This is the one thing to understand before editing anything.

- **Dispatch through the `RENDERERS` whitelist**, checked with `Object.prototype.hasOwnProperty`.
  Never `RENDERERS[molecule.type]` bare — a `type` of `"constructor"` must render an explanatory
  band, not reach into the prototype chain.
- **Treat every field as untrusted.** The payload is model output. Read it through `str()` /
  `arr()` / `bool()` / `oneOf()` in `lib/coerce.js`; never index into `molecule.metrics[0].label`
  directly. A null, a number where a string belongs, or a missing array is expected input.
- **A molecule returns `null` rather than throwing** when there is nothing to draw. Empty is normal.
- **Variant axes go through `oneOf()`** with an explicit fallback, so an unrecognised tone or band
  renders the neutral variant instead of an unstyled block.
- **Adding a molecule family is exactly two edits**: a Pydantic model in `backend/schemas.py`
  added to the `Molecule` union, and an entry in `RENDERERS`. They must stay in step.
- **Meaning→presentation mapping belongs in the component, not the schema.** The agent says
  `tone: "risk"` and `band: "low"`; `TONE_CLASSES` and `BAND_CLASSES` decide that these mean
  `.callout.alert` and `.sc-alert`. Never let a CSS class name into the agent's vocabulary.

## 3. Error handling — the page must not be able to crash

Five layers, each catching what the others cannot; **never remove one because another looks
sufficient.**

| Layer | Catches |
|---|---|
| Backend structured outputs | invented molecule types, missing props |
| Backend `_sanitize()` | valid shape, unusable content (orphan source, headerless band) |
| `lib/stream.js` frame parsing | malformed SSE frame, non-JSON data |
| Coercers + whitelist in `registry.jsx` | wrong types, nulls, unknown/hostile `type` |
| `<ErrorBoundary>` per molecule | any render-time throw |

- **Every molecule is individually wrapped in `<ErrorBoundary>`** inside the registry. One bad
  band must never blank the section.
- **The backend's own failures arrive as a renderable molecule** (a risk-toned callout), not as a
  special error shape. If the renderer can draw the failure, the renderer is the only thing that
  ever draws. Keep it that way.
- **`App.jsx`'s `.catch` handles transport failure only** — the case the backend cannot report
  because the connection died. Do not duplicate backend error copy there.
- **Never render a raw error string, stack, or upstream exception message to the user.** Generic
  prose on screen; detail to `console.error`.
- Show **streaming, empty, and error** as three distinct states. Never conflate empty with error.
- Boundaries catch render errors only — never async or event-handler errors. Those need explicit
  try/catch.

## 4. State

- **Local `useState` in `App.jsx`** is correct here. No server-state library and no router, so
  `useEffect` + stream + `setState` is the right call — but keep all `fetch` in `lib/stream.js`,
  and keep the `AbortController` so a late frame cannot set state after unmount.
- **Molecule state has two writers**: the optimistic `molecule` event writes at an index, the
  authoritative `section` event replaces the whole list. **Replace-wins is load-bearing** — it is
  how the second pass corrects the first. Do not merge them.
- **Write at the index the agent sends**, not `push`. A duplicated or out-of-order frame must land
  in one place rather than producing two copies of a band.
- **Never put side effects in a state updater.** React invokes updaters twice in development;
  starting a request inside one fires it twice. Start the request in the handler.
- **Guard a late answer against a changed subject.** The inspect pane can be closed and reopened
  on a different datapoint while a reply is in flight; append only if the subject still matches.
- **Derive, never duplicate.** `signalCount` is computed during render, not stored.
- Name state for its domain: `molecules`, `inspection`, `timings`. **Never `data`, `item`, `tmp`, `res`.**

## 5. Components & naming

| Unit | Limit |
|---|---|
| Component file | ≤ 250 lines |
| Component body | ≤ 120 lines |
| JSX nesting | ≤ 4 |
| Props | ≤ 8 |

- **Never define a component inside a component** — it remounts and loses state every parent
  render. `Row` in `ScoreTable.jsx` is module-scope for this reason.
- `handle*` for internal handlers, `on*` for props. `is/has/can/should` for booleans.
- `UPPER_SNAKE` module constants — `TONE_CLASSES`, `BAND_CLASSES`, `LOCKED_SECTIONS`. No inline
  magic numbers.
- Ternaries for conditional render, never `&&` with a possibly-numeric left side
  (`{count && <X/>}` renders a literal `0`).
- **The shell is static and must stay static.** Header, section numbers, locked sections and the
  CTA are product chrome. If the model starts choosing them, the POC no longer demonstrates a
  bounded catalog.

## 6. Accessibility

- **The DS's inspect affordance is inaccessible as exported** — clickable divs, no roles, no tab
  stops. `InspectTarget` is the fix and every inspect target must go through it. This is a real DS
  gap worth reporting upstream, not a local workaround to quietly maintain.
- Announce async arrival: streaming state and section completion go through `role="status"` +
  `aria-live="polite"`. The whole interaction is otherwise silent to a screen reader.
- Icon-only controls need an accessible name — the pane's close button uses `aria-label`.
- The review textarea has a real `<label htmlFor>`; keep it.
- Semantic elements first: `<main>`, `<aside>`, `<section>`, `<header>`, `<nav>`, real `<button>`s
  everywhere the DS is not forcing a div.
- Never encode meaning by colour alone — a coral band always carries a lead phrase or label too.
- Keep focus outlines. Body text contrast ≥ 4.5:1.

## 7. Performance

Correctness first; only optimize with a measurement. Relevant here:

- **Baseline: 203 kB JS / 64 kB gzipped, 55 kB CSS / 10 kB gzipped, one chunk.** No chart library,
  so there is nothing large to split. If this grows materially, say why in the PR.
- **`Timings.jsx` is the measurement surface.** Time-to-first-molecule vs. section-complete is the
  POC's headline claim. Never let it report a number the backend did not send.
- Stable `key`s. Molecule position is an acceptable key here **only** because the stream appends in
  order and never reorders or filters; anywhere else it is a bug.
- No `await` inside a loop; independent requests go in `Promise.all`.
- `useCallback` where it prevents real work (`appendAnswer`, `openInspection`) — not on primitives.
- Release the stream reader in a `finally`. An abandoned reader keeps the connection open and
  keeps costing tokens upstream.

## 8. Gates — honest baseline

```bash
npm run lint       # oxlint src — configless; currently CLEAN (zero findings)
npm run build      # vite build — currently passes, 203 kB / 64 kB gzipped
npm run dev        # then click through the app with the backend running
```

- **The linter is `oxlint`, not ESLint**, and it is scoped to `src` — unscoped it walks
  `node_modules` and reports hundreds of warnings from React's own dev build. `npm run lint` is a
  real gate and it is currently green: **never leave it with a new finding.**
- **There is no TypeScript and no `npm run typecheck`.**
- **There is no test framework.** If adding one: Vitest + React Testing Library. Priority order —
  `registry.jsx` against malformed and hostile payloads (highest value), the `coerce.js` edges,
  `stream.js` frame-splitting across chunk boundaries, `ErrorBoundary` containment.

`npm run build` succeeding means it compiled, **not** that it works. Run the app.

## 9. AI agent rules

1. **Read `molecules/registry.jsx` first** — it defines what can be drawn.
2. **Keep the catalog in sync with `backend/schemas.py`.** Two edits, always.
3. **Never edit `signal.css`** to restyle something. New rules go in `app.css`.
4. **Never trust the payload.** New field reads go through the coercers.
5. **Never remove an error-handling layer** (§3), and never render a raw error to a user.
6. **Never let a CSS class name into the agent's schema**, and never let the agent choose page
   structure — only section content.
7. No new dependency without asking — the runtime dependency list is deliberately two entries.
8. **Run `npm run lint` and `npm run build`, load the app, and report real output.** Do not claim
   a typecheck or test that does not exist here.
9. Keep the diff focused. No drive-by refactors, no reformatting untouched files, no commits
   unless asked.
10. Plain JSX. Do not introduce `.tsx` files piecemeal.

## 10. Review checklist

**Registry** — whitelist dispatch intact (`hasOwnProperty`, not a bare index)? new field reads
coerced? variant axes through `oneOf()` with a fallback? molecule returns `null` instead of
throwing on empty? new type registered in both `RENDERERS` and the backend union?

**Design system** — `signal.css` edited (should be `app.css`)? an invented DS class name? a column
width set on a row grid? a band wrapped in a `<button>` instead of `InspectTarget`?

**Errors** — every molecule still inside an `<ErrorBoundary>`? backend failure still arriving as a
renderable molecule? any raw error message, stack, or exception text rendered to the user? empty
`catch`? streaming/empty/error all distinct?

**State** — side effect inside a state updater? optimistic and authoritative writers merged? `push`
instead of index write? stale-response guard on subject present? abort on unmount? identifier named
`data`/`tmp`/`item`?

**Components** — component defined inside a component? file over 250 lines? `&&` with a numeric left
side? shell chrome quietly becoming model-driven?

**A11y** — inspect target bypassing `InspectTarget`? icon-only button without a name? textarea
without a label? async arrival unannounced? status by colour alone? focus outline removed?

**Gates** — `npm run lint` and `npm run build` actually run and reported? no claim of typecheck or
tests, which do not exist in this project?
