import { bool, capabilityClasses, oneOf, str } from '../lib/coerce.js';
import InspectTarget from './InspectTarget.jsx';

/**
 * DS §3.2 — the banded component.
 *
 * One component, three line colours. The annotation is explicit that there is no
 * separate "intel card": an intel insight is this same band with an optional
 * header row. The stylesheet still ships two classes for it (`.callout` and
 * `.intel-card`), so this component is the single place that reconciles them —
 * one React component, the DS's stated intent, mapped onto the CSS as exported.
 *
 * The tone → class map is the whole meaning→presentation seam. The agent says
 * what a statement *is*; this decides what it looks like.
 */
const TONE_CLASSES = {
  // Navy line — context and facts, including prospect-intel insights.
  context: 'intel-card',
  // Teal line — recommendations and confirmations. `.callout`'s default.
  recommendation: 'callout',
  // Coral line — risks and unreviewed signals.
  risk: 'callout alert',
};

const TONES = Object.keys(TONE_CLASSES);

const SUBJECT_MAX = 80;

export default function Callout({ molecule, onInspect }) {
  const body = str(molecule.body);
  if (!body) return null;

  const tone = oneOf(molecule.tone, TONES, 'context');
  const lead = str(molecule.lead);
  const label = str(molecule.label);
  const source = str(molecule.source);
  // DS §3.2: the intel header is a label plus an italic source line. The backend
  // drops an orphan source, but a payload can reach here by other routes.
  const hasHeader = Boolean(label);

  const isInspectable = bool(molecule.inspect) && Boolean(onInspect);
  const subject = label || lead || `${body.slice(0, SUBJECT_MAX)}…`;

  return (
    <InspectTarget
      className={capabilityClasses(TONE_CLASSES[tone], molecule)}
      label={subject}
      onInspect={isInspectable ? onInspect : undefined}
    >
      {hasHeader ? (
        <div className="intel-head">
          <div className="intel-label">{label}</div>
          {source ? <div className="intel-source">{source}</div> : null}
        </div>
      ) : null}
      <div className={hasHeader ? 'intel-body' : undefined}>
        {lead ? <span className="lead">{lead} </span> : null}
        {body}
      </div>
    </InspectTarget>
  );
}
