import { arr, bool, str } from '../lib/coerce.js';
import InspectTarget from './InspectTarget.jsx';

/**
 * DS §3.4 — the phase card family.
 *
 * Navy left band, a head row carrying tag + name on the left and the timeframe on
 * the right, then dot-bulleted scope. The bullet glyphs come from
 * `.phase-card li::before`, so the list carries none of its own and the
 * `list-style: none` is the design system's.
 *
 * One molecule draws the whole plan, because `.phase-card + .phase-card` is how
 * the DS spaces them — adjacent siblings, with no container class of its own. The
 * wrapper here is deliberately classless: inventing a `.phase-plan` would be a DS
 * class name that the stylesheet has never heard of, and the cards space
 * themselves without one.
 */

/**
 * One card. Module scope rather than nested, since a component defined inside a
 * component remounts on every parent render.
 */
function Card({ phase, onInspect }) {
  const tag = str(phase?.tag);
  const name = str(phase?.name);
  const when = str(phase?.when);
  const note = str(phase?.note);
  const scope = arr(phase?.scope)
    .map((line) => str(line))
    .filter(Boolean);

  // A card with no head at all would draw as an empty navy band.
  if (!tag && !name) return null;

  return (
    <InspectTarget
      className={onInspect ? 'phase-card inspect' : 'phase-card'}
      label={`the "${name || tag}" phase`}
      onInspect={onInspect}
    >
      <div className="phase-head">
        <div>
          {tag ? <span className="phase-tag">{tag}</span> : null}
          {name ? <span className="phase-name">{name}</span> : null}
        </div>
        {when || note ? (
          <div className="phase-meta">
            {/* DS §3.4 bolds the timeframe and leaves the qualifier after the
                separator in the lighter weight. */}
            {when ? <strong>{when}</strong> : null}
            {when && note ? ' · ' : null}
            {note}
          </div>
        ) : null}
      </div>

      {scope.length > 0 ? (
        <ul>
          {scope.map((line, index) => (
            <li key={`${line}-${index}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </InspectTarget>
  );
}

export default function PhasePlan({ molecule, onInspect }) {
  const phases = arr(molecule.phases).filter((phase) => str(phase?.tag) || str(phase?.name));
  if (phases.length === 0) return null;

  // Per-card, matching DS §3.4's "all are whole-card inspect targets" — and the
  // granularity a question is actually about is one phase, not the plan.
  const inspectPhase = bool(molecule.inspect) && onInspect ? onInspect : undefined;

  return (
    <div>
      {phases.map((phase, index) => (
        <Card key={`${str(phase.tag)}-${index}`} phase={phase} onInspect={inspectPhase} />
      ))}
    </div>
  );
}
