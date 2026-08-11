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
      <span className="small-label" style={{ margin: 0 }}>
        Measured
      </span>
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
