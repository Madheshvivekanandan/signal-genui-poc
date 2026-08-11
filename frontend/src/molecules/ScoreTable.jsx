import { arr, bool, oneOf, str } from '../lib/coerce.js';
import InspectTarget from './InspectTarget.jsx';

/**
 * DS §3.3 — the score row family.
 *
 * Rows sit on an inner surface and share a fixed grid; the total row reuses that
 * grid exactly so the columns align. The annotation is blunt about this — "the
 * row grids are the spec — keep them" — so the grid lives in signal.css and
 * nothing here sets a column width.
 */

/**
 * The agent states a band as a meaning; the design system names its classes after
 * appearance. Mapping here keeps CSS naming out of the agent's contract.
 */
const BAND_CLASSES = {
  high: 'sc-good',
  mid: 'sc-mid',
  low: 'sc-alert',
};

const BANDS = Object.keys(BAND_CLASSES);

/**
 * One row. Module scope, not nested in ScoreTable — a component defined inside a
 * component remounts on every parent render.
 */
function Row({ row, isTotal, onInspect }) {
  const name = str(row?.name);
  const score = str(row?.score);
  const band = oneOf(row?.band, BANDS, 'mid');

  // DS §3.3: rows are whole-row inspect targets. The total is not one — there is
  // no "how did you get this" for a figure that is just the rows added up.
  const classes = ['score-row'];
  if (isTotal) classes.push('score-total');
  if (onInspect) classes.push('inspect');

  return (
    <InspectTarget
      className={classes.join(' ')}
      label={`the "${name}" score of ${score}`}
      onInspect={onInspect}
    >
      <div className="sc-name">{name}</div>
      <div className="sc-weight">{str(row?.weight)}</div>
      {/* The total's figure is always navy per DS §3.3, so it takes no band. */}
      <div className={isTotal ? 'sc-score' : `sc-score ${BAND_CLASSES[band]}`}>{score}</div>
      <div className="sc-note">{str(row?.note)}</div>
    </InspectTarget>
  );
}

export default function ScoreTable({ molecule, onInspect }) {
  const rows = arr(molecule.rows).filter((row) => str(row?.name));
  if (rows.length === 0) return null;

  const inspectRow = bool(molecule.inspect) && onInspect ? onInspect : undefined;

  return (
    <div className="inner-surface">
      <div className="score-table">
        {rows.map((row, index) => (
          <Row key={`${str(row.name)}-${index}`} row={row} onInspect={inspectRow} />
        ))}
        {molecule.total ? <Row row={molecule.total} isTotal /> : null}
      </div>
    </div>
  );
}
