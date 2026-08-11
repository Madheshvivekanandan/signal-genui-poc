import Callout from './Callout.jsx';
import ErrorBoundary from '../components/ErrorBoundary.jsx';
import MetricGrid from './MetricGrid.jsx';
import ScoreTable from './ScoreTable.jsx';

/**
 * The whitelist. A molecule `type` becomes DOM here and nowhere else.
 *
 * This is the file to read first. Adding a molecule family is exactly two edits —
 * a Pydantic model in `backend/schemas.py` and an entry here — and the two must
 * stay in step, because the backend's union is what the agent is allowed to emit
 * and this map is what can actually be drawn.
 */
const RENDERERS = {
  metric_grid: MetricGrid,
  callout: Callout,
  score_table: ScoreTable,
};

/** The families this build can draw, for the debug readout. */
export const KNOWN_TYPES = Object.keys(RENDERERS);

/**
 * Render one molecule.
 *
 * Dispatch goes through `hasOwnProperty` rather than a bare index so a `type` of
 * `"constructor"` or `"__proto__"` cannot reach into the prototype chain and
 * return something that is not a component. The payload is model output; an
 * unknown or hostile `type` is expected input, and it renders an explanatory band
 * instead of throwing.
 */
export default function Molecule({ molecule, onInspect }) {
  const type = typeof molecule?.type === 'string' ? molecule.type : '';

  if (!Object.prototype.hasOwnProperty.call(RENDERERS, type)) {
    return (
      <div className="callout alert">
        <span className="lead">Unknown component.</span> The agent asked for a
        {type ? ` "${type}"` : 'n unnamed'} molecule, which this build cannot draw.
      </div>
    );
  }

  const Renderer = RENDERERS[type];

  // Per molecule, so one malformed payload costs its own band and not the section.
  return (
    <ErrorBoundary>
      <Renderer molecule={molecule} onInspect={onInspect} />
    </ErrorBoundary>
  );
}
