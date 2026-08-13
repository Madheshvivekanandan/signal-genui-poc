import { A2uiSurface } from '@a2ui/react/v0_9';

import { arr, bool, str } from '../lib/coerce.js';

/**
 * The agent's whole vocabulary — every component it may choose from, drawn.
 *
 * The claim this POC rests on is that the model picks from a closed set and
 * cannot invent anything. That claim is only checkable if the set is visible, and
 * a list of three names does not show what a `callout` *is*. So each family
 * arrives twice over: as a specimen, and as the field table the model is handed.
 *
 * **The specimens are not mocks.** They are real molecules, compiled by
 * `backend/a2ui.py` and drawn by `A2uiSurface` against the same catalog that
 * renders the section above — the same path, the same components. What is on
 * screen here is what the agent gets to use.
 *
 * The field tables are introspected from `backend/schemas.py`, including each
 * field's `description`, which is the prose the model actually reads: Pydantic
 * puts it in the JSON Schema and the JSON Schema is the structured-output format.
 * Nothing here is written out by hand, so nothing here can drift from what is
 * really sent.
 *
 * It sits at the bottom of the page, below the inspector, because it is reference
 * material about the system rather than a reading of the current document.
 */

function Bounds({ bounds, choices }) {
  const options = arr(choices);
  if (options.length > 0) {
    return (
      <span className="cat-choices">
        {options.map((choice) => (
          <code key={choice} className="cat-choice">
            {choice}
          </code>
        ))}
      </span>
    );
  }

  const min = bounds?.min;
  const max = bounds?.max;
  if (min == null && max == null) return null;
  if (min != null && max != null) {
    return <span className="cat-bound">{min === max ? min : `${min}–${max}`}</span>;
  }
  return <span className="cat-bound">{min != null ? `min ${min}` : `max ${max}`}</span>;
}

function FieldTable({ fields }) {
  return (
    <table className="cat-fields">
      <thead>
        <tr>
          <th>Field</th>
          <th>Type</th>
          <th>What the model is told it is for</th>
        </tr>
      </thead>
      <tbody>
        {arr(fields).map((field) => (
          <tr key={str(field?.name)}>
            <td>
              <code>{str(field?.name)}</code>
              {bool(field?.required) ? <span className="cat-req">required</span> : null}
            </td>
            <td>
              <span className="cat-type">{str(field?.type)}</span>
              <Bounds bounds={field?.bounds} choices={field?.choices} />
            </td>
            <td className="cat-desc">{str(field?.description) || '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Family({ family, surface }) {
  const nested = arr(family?.nested);

  return (
    <section className="cat-family">
      <h4>
        <code className="cat-name">{str(family?.type)}</code>
        <span className="cat-arrow">→</span>
        <code className="cat-component">{str(family?.component)}</code>
        <em>{str(family?.summary)}</em>
      </h4>

      {/* The specimen. Drawn by A2UI from the same catalog as the section above —
          if this renders, the component is real. */}
      <div className="cat-specimen">
        {surface ? (
          <A2uiSurface surface={surface} />
        ) : (
          <p className="cat-note">Specimen not loaded.</p>
        )}
      </div>

      <FieldTable fields={family?.fields} />

      {nested.map((sub) => (
        <div key={str(sub?.name)} className="cat-nested">
          <h5>
            <code>{str(sub?.name)}</code>
            <em>{str(sub?.summary)}</em>
          </h5>
          <FieldTable fields={sub?.fields} />
        </div>
      ))}
    </section>
  );
}

export default function MoleculeCatalog({ catalog, surfaces }) {
  const families = arr(catalog?.families);
  const maxMolecules = catalog?.max_molecules;

  return (
    <section className="catalog" aria-label="The molecule catalog offered to the agent">
      <div className="cat-head">
        <span className="small-label" style={{ margin: 0 }}>
          The catalog offered to the agent
        </span>
        {families.length > 0 ? (
          <span className="cat-count">
            {families.length} families · at most {maxMolecules ?? '—'} per section
          </span>
        ) : null}
      </div>

      <p className="cat-intro">
        Everything the model may return, and nothing else. Choosing among these is its decision,
        and the whole of it — which family a statement becomes is the design decision this POC
        hands the agent. What it never does is name the A2UI component that draws its choice,
        write a binding path, or pick a colour; the compiler owns those. The specimens below are
        drawn by the same catalog that renders the section above; the field tables are read out
        of the schema the model is actually given.
      </p>

      {families.length > 0 ? (
        families.map((family) => (
          <Family
            key={str(family?.type)}
            family={family}
            surface={surfaces?.get(str(family?.surface_id)) ?? null}
          />
        ))
      ) : (
        <p className="cat-note">The catalog could not be loaded.</p>
      )}

      <p className="cat-foot">
        Specimens carry <code>inspect: false</code>, so clicking one does not open the review
        pane. Adding a fourth family is three edits that must stay in step: a model in the{' '}
        <code>Molecule</code> union, a <code>_VIEW</code> row in the compiler, and a component
        registered in the frontend catalog.
      </p>
    </section>
  );
}
