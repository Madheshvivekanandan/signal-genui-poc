import { arr, bool, str } from '../lib/coerce.js';
import InspectTarget from './InspectTarget.jsx';

/**
 * DS §3.1 — metric tiles.
 *
 * Top-line facts for a section. Label 14/caps, value 17/600, sub 15,
 * left-aligned, no surface of its own. "Grids of 3 or 4", so the column count
 * follows the data rather than being fixed at three.
 */
export default function MetricGrid({ molecule, onInspect }) {
  const metrics = arr(molecule.metrics).filter(
    (metric) => str(metric?.label) || str(metric?.value),
  );
  if (metrics.length === 0) return null;

  // DS §3.1: "metrics can be inspect targets when the number deserves a 'how did
  // you get this'". The capability is declared on the grid; it applies per tile,
  // because that is the granularity a question is actually about.
  const isInspectable = bool(molecule.inspect) && Boolean(onInspect);

  return (
    <div className="metric-grid" style={{ gridTemplateColumns: `repeat(${metrics.length}, 1fr)` }}>
      {metrics.map((metric, index) => {
        const label = str(metric.label);
        const value = str(metric.value);
        const sub = str(metric.sub);

        return (
          <InspectTarget
            key={`${label}-${index}`}
            className={isInspectable ? 'metric inspect' : 'metric'}
            label={`the "${label}" metric, currently reading ${value}`}
            onInspect={isInspectable ? onInspect : undefined}
          >
            <div className="label">{label}</div>
            <div className="value">{value}</div>
            {sub ? <div className="sub">{sub}</div> : null}
          </InspectTarget>
        );
      })}
    </div>
  );
}
