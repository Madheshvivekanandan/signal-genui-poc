---
name: react-best-practices
description: React standard for the signal-genui-poc frontend — a Vite + React 19 SPA (plain JSX, no TypeScript) that renders a fixed Signal design-system page whose section bodies are composed by an agent and drawn by A2UI v0.9 from a closed component catalog. Load BEFORE writing, modifying, or reviewing any frontend code in this repo — anything under frontend/src/ (App.jsx, a2ui/, molecules/, shell/, lib/) or any .jsx/.css file. Covers the vendored design system, the A2UI catalog contract and binding rules, defensive rendering, error boundaries, surface/state ownership, a11y, performance, and a review checklist.
---

# React Best Practices — signal-genui-poc frontend

Correctness and clarity first, then performance. Adapted from React docs, Vercel
Engineering's react-best-practices (MIT), and WCAG, cut down to what this app is.
**When this document conflicts with the existing code, follow the code and say so.**

## 0. This project — the actual stack

```
frontend/src/
  main.jsx                 # entry; imports signal.css THEN app.css
  App.jsx                  # the MessageProcessor, chrome state, inspect state
  signal.css               # VENDORED design system — treat as read-only
  app.css                  # POC-only styles the DS does not define
  a2ui/
    catalog.jsx            # the A2UI component catalog — the heart of the app
    messages.js            # the two A2UI messages the client builds itself
  lib/
    stream.js              # the ENTIRE backend contract — the only place fetch appears
    coerce.js              # untrusted-payload coercers + capability classes
  molecules/
    MetricGrid.jsx  Callout.jsx  ScoreTable.jsx  InspectTarget.jsx
  shell/
    Header.jsx  Section.jsx  ReviewPane.jsx
    Timings.jsx            # renders as the inspector's stage 4, not on the page
    DocumentPicker.jsx     # demo surface: switch document, section re-composes
    MoleculeCatalog.jsx    # demo surface: the vocabulary + live specimens, from /api/catalog
    ProtocolInspector.jsx  # demo surface: agent JSON → compile → frames → measured. Renders nothing.
  components/
    ErrorBoundary.jsx
```

- **Vite + React 19, plain JSX. There is no TypeScript**, no `tsc`, no type-checking gate.
- **Five runtime dependencies**: `react`, `react-dom`, `@a2ui/react`, `@a2ui/web_core`, `zod`.
  No charting library, no router, no state library, no data-fetching library. It was two before
  the A2UI migration; do not add a sixth without asking.
- **`zod` must stay on v3.** A2UI's binder classifies props by reading Zod 3 internals
  (`_def.typeName`). Zod 4 renamed them and the failure is silent — every prop degrades to
  `STATIC` and bindings render as `[object Object]`.
- **A2UI v0.9, not v1.0.** Import from `@a2ui/react/v0_9` and `@a2ui/web_core/v0_9`. There is no
  v1.0 entry point in the installed package; v1.0 is still a spec Candidate.
- **Plain CSS.** `signal.css` is lifted from the Signal DS HTML export; `app.css` holds only
  what the DS lacks. **None of A2UI's stylesheets are imported** — see §2.

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

## 2. The A2UI catalog contract

The backend sends A2UI v0.9 messages. `a2ui/catalog.jsx` declares what those messages are allowed
to name, and A2UI's renderer turns them into DOM. This is the one thing to understand before
editing anything.

- **The catalog is the whitelist.** A component name the agent invents is rejected by the renderer
  before it reaches our code. This replaced a `hasOwnProperty` dispatch and is stronger, because
  the library enforces it. Component names are matched against a catalog map and never used to
  index an object, so the old prototype-pollution concern no longer applies.
- **Four components, and A2UI's basic catalog is deliberately NOT registered.** `Column`, `Row`
  and `Card` inject their own flex styles and `--a2ui-*` spacing variables, which compete with
  `signal.css` for control of the section body. `MoleculeStack` is the only structural component
  and it draws the DS's own `.molecule-stack`. **Do not register `basicCatalog`'s components** —
  it would import A2UI's stylesheets and create a cascade to reconcile.
- **Declare each component twice**: a Zod schema (what may be set, and which props accept a
  `{path: …}` binding) and a React implementation receiving resolved values. The binder sits
  between them; implementations never see a binding object.
- **Every prop is `.optional()`.** The data model is written by an agent and can be mid-stream
  when a component first renders. A missing prop must not be a schema violation.
- **The schema classifies, it does not validate.** `scrapeSchemaBehavior` reads the schema to
  decide `DYNAMIC` / `STRUCTURAL` / `ACTION` / `STATIC`; resolved values are passed through
  untouched. That is why binding an object (`score_table.total`) to a `DynamicValue` works even
  though the union has no object member.
- **Treat every field as untrusted.** Resolved values are still model output. Read them through
  `str()` / `arr()` / `bool()` / `oneOf()` in `lib/coerce.js`; never index into
  `molecule.metrics[0].label` directly.
- **A molecule returns `null` rather than throwing** when there is nothing to draw. Empty is normal.
- **Variant axes go through `oneOf()`** with an explicit fallback, so an unrecognised tone or band
  renders the neutral variant instead of an unstyled block.
- **Adding a molecule family is exactly three edits**: a Pydantic model added to the `Molecule`
  union in `backend/schemas.py`, a `_VIEW` row in `backend/a2ui.py`, and a component registered
  here. All three must stay in step.
- **Meaning→presentation mapping belongs in the component, not the schema.** The agent says
  `tone: "risk"` and `band: "low"`; `TONE_CLASSES` and `BAND_CLASSES` decide that these mean
  `.callout.alert` and `.sc-alert`. Never let a CSS class name into the agent's vocabulary, and
  never let an A2UI component name into it either — the compiler owns that mapping.
- **Interaction goes through `context.dispatchAction`**, not a React callback threaded down. The
  inspect click is a real A2UI action; `App.jsx`'s `MessageProcessor` handler receives it.

## 3. Error handling — the page must not be able to crash

Five layers, each catching what the others cannot; **never remove one because another looks
sufficient.**

| Layer | Catches |
|---|---|
| Backend structured outputs | invented molecule types, missing props |
| Backend `_sanitize()` | valid shape, unusable content (orphan source, headerless band) |
| `lib/stream.js` frame parsing | malformed SSE frame, non-JSON data |
| A2UI catalog validation | unknown component name, malformed component definition |
| Coercers in the molecules | wrong types, nulls, a number where a string belongs |
| `<ErrorBoundary>` per molecule | any render-time throw |

- **Every molecule is individually wrapped in `<ErrorBoundary>`** inside its catalog
  implementation. One bad band must never blank the section — and a boundary around the whole
  surface would let one malformed payload blank the agent's entire answer.
- **`processor.processMessages` is wrapped in try/catch at every call site.** A message the
  renderer rejects is our bug, not the user's: log it and let the authoritative pass resend.
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

- **Molecules are NOT React state.** They live in the `MessageProcessor`'s surface data model,
  which is externally owned and mutated in place. `App.jsx` holds only chrome — header, subtitle,
  counts, timings, which datapoint is being inspected — plus a snapshot of *which surfaces exist*.
- **Re-snapshot `surfacesMap` on the processor's own create/delete events**, never on a timer and
  never by mirroring content. React cannot observe an in-place mutation; `A2uiSurface` handles
  content updates itself through the reactive binder.
- **Build the `MessageProcessor` in a `useMemo` with a stable dep list.** Rebuilding it discards
  every surface it holds. The action handler reaching `openInspection` through a ref exists for
  exactly this reason — do not "simplify" it into a dependency.
- **Counts come from the backend's `meta` channel**, because the client can no longer derive them
  from React state. Never reach into the processor's internals to recompute them.
- **Local `useState` in `App.jsx`** is correct for the chrome. No server-state library and no
  router, so `useEffect` + stream + `setState` is the right call — but keep all `fetch` in
  `lib/stream.js`, and keep the `AbortController` so a late frame cannot set state after unmount.
- **The two writers are now both A2UI passes**: the optimistic pass sends `updateDataModel` +
  `updateComponents` for one new molecule, the authoritative pass replaces the whole surface.
  **Replace-wins is load-bearing** — it is how the second pass corrects the first. Both emit the
  same message types; the difference is the source of truth. Do not collapse them.
- **Delete inspect surfaces when the pane closes.** An answer can attach its own surface, and
  dropping the turns without a `deleteSurface` leaks one per question asked.
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
- `UPPER_SNAKE` module constants — `TONE_CLASSES`, `BAND_CLASSES`, `MAX_FRAMES`. No inline
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

- **Baseline: 371 kB JS / 108 kB gzipped, 55 kB CSS / 10 kB gzipped, one chunk, 413 modules.**
  A2UI's renderer and binder are ~44 kB gzipped of that; it was 203 kB / 64 kB / 29 modules
  before the migration. If this grows materially again, say why in the PR.
- **`Timings.jsx` is the measurement surface.** Time-to-first-molecule vs. section-complete is the
  POC's headline claim. Never let it report a number the backend did not send. It renders only
  once `total_ms` arrives — `meta` frames also carry running counts mid-stream, so presence alone
  does not mean the section finished.
- Stable `key`s. In `MoleculeStack`, children are keyed by A2UI component id, which is stable
  across both passes. Never key by array position there.
- No `await` inside a loop; independent requests go in `Promise.all`.
- `useCallback` where it prevents real work (`appendAnswer`, `openInspection`) — not on primitives.
- Release the stream reader in a `finally`. An abandoned reader keeps the connection open and
  keeps costing tokens upstream.

## 8. Gates — honest baseline

```bash
npm run lint       # oxlint src — configless; currently CLEAN (zero findings)
npm run build      # vite build — currently passes, 371 kB / 108 kB gzipped
npm run dev        # then click through the app with the backend running
```

- **The linter is `oxlint`, not ESLint**, and it is scoped to `src` — unscoped it walks
  `node_modules` and reports hundreds of warnings from React's own dev build. `npm run lint` is a
  real gate and it is currently green: **never leave it with a new finding.**
- **There is no TypeScript and no `npm run typecheck`.**
- **There is no test framework.** If adding one: Vitest + React Testing Library. Priority order —
  `a2ui/catalog.jsx` binding resolution against malformed payloads (highest value), the
  `coerce.js` edges,
  `stream.js` frame-splitting across chunk boundaries, `ErrorBoundary` containment.

`npm run build` succeeding means it compiled, **not** that it works. Run the app.

## 9. AI agent rules

1. **Read `a2ui/catalog.jsx` first** — it defines what can be drawn. Then `backend/a2ui.py`,
   which decides what gets asked for.
2. **Keep the catalog in sync with `backend/schemas.py` and `backend/a2ui.py`.** Three edits,
   always. A component in the catalog with no `_VIEW` row is dead code; a `_VIEW` row with no
   catalog entry is a render failure.
3. **Never edit `signal.css`** to restyle something. New rules go in `app.css`.
4. **Never trust the payload.** New field reads go through the coercers, resolved or not.
5. **Never remove an error-handling layer** (§3), and never render a raw error to a user.
6. **Never let a CSS class name or an A2UI component name into the agent's schema**, and never let
   the agent choose page structure — only section content.
7. No new dependency without asking — the list is five entries and was deliberately two.
   **Never register A2UI's `basicCatalog` components** (§2), and never bump `zod` to v4 (§0).
8. **Run `npm run lint` and `npm run build`, load the app, and report real output.** Do not claim
   a typecheck or test that does not exist here.
9. Keep the diff focused. No drive-by refactors, no reformatting untouched files, no commits
   unless asked.
10. Plain JSX. Do not introduce `.tsx` files piecemeal.

## 10. Review checklist

**Catalog** — new component registered in all three places (schema union, `_VIEW`, catalog)? every
prop `.optional()`? A2UI stylesheets still unimported and `basicCatalog` components still
unregistered? new field reads coerced? variant axes through `oneOf()` with a fallback? molecule
returns `null` instead of throwing on empty? interaction through `context.dispatchAction` rather
than a threaded callback?

**Protocol** — imports from the `v0_9` entry points, not the package root? `zod` still v3?
`CATALOG_ID` identical on both sides? `processMessages` inside a try/catch? data sent before the
components that bind to it?

**Design system** — `signal.css` edited (should be `app.css`)? an invented DS class name? a column
width set on a row grid? a band wrapped in a `<button>` instead of `InspectTarget`?

**Errors** — every molecule still inside an `<ErrorBoundary>`? backend failure still arriving as a
renderable molecule? any raw error message, stack, or exception text rendered to the user? empty
`catch`? streaming/empty/error all distinct?

**State** — side effect inside a state updater? optimistic and authoritative passes merged?
molecules mirrored into React state instead of left in the surface? `MessageProcessor` rebuilt on
render (losing every surface)? inspect surfaces deleted on pane close? stale-response guard on
subject present? abort on unmount? identifier named `data`/`tmp`/`item`?

**Components** — component defined inside a component? file over 250 lines? `&&` with a numeric left
side? shell chrome quietly becoming model-driven?

**A11y** — inspect target bypassing `InspectTarget`? icon-only button without a name? textarea
without a label? async arrival unannounced? status by colour alone? focus outline removed?

**Gates** — `npm run lint` and `npm run build` actually run and reported? no claim of typecheck or
tests, which do not exist in this project?
