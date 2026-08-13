/**
 * The measurement readout.
 *
 * Whether this approach lags was the open question behind the POC. This puts the
 * answer on screen instead of in a claim: how long until the first molecule was
 * painted, how long
 * the whole section took, and how many components came back.
 *
 * Time-to-first-molecule is the number that matters. Total time is roughly what a
 * non-streaming implementation would make the user wait, so the gap between the
 * two is what streaming actually buys — stated, not asserted.
 *
 * It renders as the inspector's fourth stage rather than as its own strip on the
 * page. Instrumentation belongs with instrumentation, and the inspector is
 * already the surface that answers "what actually happened". The heading there
 * carries the "Measured" label, so this renders the figures only.
 */
export default function Timings({ timings, moleculeCount }) {
  // `meta` frames now also carry running counts during the stream, so presence
  // alone no longer means the section finished. The completed measurement is
  // what this readout is for, and `total_ms` is what marks it.
  if (!timings || timings.total_ms == null) return null;

  const firstPaint = timings.first_molecule_ms;
  const total = timings.total_ms;
  const saved = firstPaint != null && total != null ? total - firstPaint : null;

  return (
    <div className="timings" role="status">
      <dl>
        <div>
          <dt>First component painted</dt>
          <dd>{firstPaint != null ? `${firstPaint} ms` : 'not streamed'}</dd>
        </div>
        <div>
          <dt>Section complete</dt>
          <dd>{total != null ? `${total} ms` : '—'}</dd>
        </div>
        <div>
          <dt>Components</dt>
          <dd>{moleculeCount}</dd>
        </div>
        {saved != null ? (
          <div>
            <dt>Wait avoided by streaming</dt>
            <dd>{saved} ms</dd>
          </div>
        ) : null}
        {/* The other half of "is this viable": what the generation cost. Absent
            when the API did not report usage, rather than shown as zero. */}
        {timings.tokens ? (
          <div>
            <dt>Tokens in / out</dt>
            <dd>
              {timings.tokens.prompt?.toLocaleString()} /{' '}
              {timings.tokens.completion?.toLocaleString()}
            </dd>
          </div>
        ) : null}
      </dl>
      {timings.ok === false ? (
        <p className="timings-error">
          The agent reported a failure ({timings.error}). The section above shows the
          fallback.
        </p>
      ) : null}
    </div>
  );
}
