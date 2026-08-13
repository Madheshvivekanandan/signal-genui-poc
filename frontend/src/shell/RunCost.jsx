/**
 * What this section cost, beside the section it paid for.
 *
 * The POC's open question was whether generating an interface per document is
 * fast enough and cheap enough to be a real product decision rather than a demo
 * trick. Both halves of that answer are numbers, and they are most useful next to
 * the thing they measure — reading "6.2s, 3,400 tokens" while looking at the six
 * components it bought is a different kind of understanding from reading it in a
 * panel further down the page.
 *
 * Styled as instrumentation on purpose, not as product. It sits inside a
 * design-system surface, which is the one place in this build where that
 * distinction could get blurred, so it stays muted, mono-figured and separated by
 * a hairline: nothing here should read as something the design system specifies.
 *
 * Values arrive on the `meta` channel and are absent until the authoritative pass
 * lands. Absent renders nothing rather than zeros — a run still streaming and a
 * run that cost nothing are different facts.
 */

/** A count off the wire, formatted, or a dash. */
function count(value) {
  return Number.isFinite(value) ? value.toLocaleString() : '—';
}

/** Milliseconds as the unit that reads best at that magnitude. */
function duration(ms) {
  if (!Number.isFinite(ms)) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

function Row({ label, value, hint }) {
  return (
    <div className="rc-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
      {hint ? <p className="rc-hint">{hint}</p> : null}
    </div>
  );
}

export default function RunCost({ meta, moleculeCount, isStreaming }) {
  // `meta` carries running counts mid-stream, so its presence does not mean the
  // run finished. `total_ms` is what marks a completed measurement.
  const isDone = meta?.total_ms != null;
  if (isStreaming || !isDone) return null;

  const firstPaint = meta.first_molecule_ms;
  const total = meta.total_ms;
  const tokens = meta.tokens ?? null;

  return (
    <aside className="run-cost" aria-label="What this section cost to generate">
      <p className="rc-head">This section</p>

      <dl>
        <Row
          label="First component"
          value={duration(firstPaint)}
          hint={firstPaint != null ? 'when the page stopped being empty' : undefined}
        />
        <Row label="Complete" value={duration(total)} hint="all components final" />
        <Row label="Components" value={count(moleculeCount)} />
      </dl>

      {/* Unknown usage is reported as unknown. Printing 0 would be a lie about
          cost, which is the one number here somebody might budget against. */}
      {tokens ? (
        <dl className="rc-tokens">
          <Row label="Tokens in" value={count(tokens.prompt)} hint="prompt + document" />
          <Row label="Tokens out" value={count(tokens.completion)} hint="the molecules" />
          <Row label="Total" value={count(tokens.total)} />
        </dl>
      ) : (
        <p className="rc-unknown">Token usage not reported for this run.</p>
      )}

      {meta.model ? <p className="rc-model">{meta.model}</p> : null}
    </aside>
  );
}
