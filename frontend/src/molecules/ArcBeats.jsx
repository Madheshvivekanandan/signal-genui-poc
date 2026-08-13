import { arr, bool, str } from '../lib/coerce.js';
import InspectTarget from './InspectTarget.jsx';

/**
 * DS §3.4 — the story arc, as three-up tiles on inner surfaces.
 *
 * `.arc-beats` is `repeat(3, 1fr)`, which the schema enforces rather than the
 * component patches: three beats or none. Rendering two would leave a visible
 * empty column, and overriding the grid to fit would move a layout decision out
 * of the design system and into here.
 *
 * The beats are the one family whose content is a judgement rather than a
 * restatement — how to open, turn and close against this opportunity — so they
 * are natural inspect targets and the DS makes each tile a whole-card one.
 */
export default function ArcBeats({ molecule, onInspect }) {
  const beats = arr(molecule.beats).filter((beat) => str(beat?.text));
  if (beats.length === 0) return null;

  const isInspectable = bool(molecule.inspect) && Boolean(onInspect);

  return (
    <div className="arc-beats">
      {beats.map((beat, index) => {
        const label = str(beat.label);
        const text = str(beat.text);

        return (
          <InspectTarget
            key={`${label}-${index}`}
            className={isInspectable ? 'arc-beat inspect' : 'arc-beat'}
            label={`the "${label}" beat of the story arc`}
            onInspect={isInspectable ? onInspect : undefined}
          >
            {label ? <div className="b-label">{label}</div> : null}
            <div className="b-text">{text}</div>
          </InspectTarget>
        );
      })}
    </div>
  );
}
