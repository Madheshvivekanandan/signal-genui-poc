/**
 * One molecule, followed from the system prompt to the pixels.
 *
 * The protocol inspector already shows every transformation — but it shows them
 * for the whole section at once, in parallel panes, which is the right shape for
 * diagnosing a run and the wrong shape for explaining one. Nobody follows five
 * molecules through four stages simultaneously while somebody talks over it.
 *
 * So this is the same information rearranged for an audience: one molecule, six
 * numbered stages, in order, each showing the artifact that stage produced. The
 * last stage draws the molecule for real — same renderer, same catalog, its own
 * surface — so the chain ends in pixels rather than in a claim about pixels.
 *
 * Everything here comes off the `trace` channel of the run that just happened.
 * Nothing is written out, which is the property that makes it worth showing: the
 * prompt is the prompt that was sent, the JSON is what the model returned, the
 * bindings are what the compiler emitted.
 */

import { A2uiSurface } from '@a2ui/react/v0_9';

import { arr, str } from '../lib/coerce.js';

/** Pretty-print for a display pane. Never throws on a value off the wire. */
function pretty(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '—';
  }
}

function Stage({ step, title, note, children }) {
  return (
    <section className="wt-stage">
      <h4>
        <span className="insp-step">{step}</span>
        {title}
      </h4>
      {note ? <p className="wt-note">{note}</p> : null}
      {children}
    </section>
  );
}

/**
 * Stage 1. Both halves of the prompt, and the thing the prompt does not carry.
 *
 * The split is not presentational: the standing instructions are assembled once
 * and the document is appended per request, which is what stops one document's
 * peculiarities travelling to the next one.
 */
function Prompt({ trace }) {
  const instructions = str(trace?.instructions);
  const document = str(trace?.document_text);

  return (
    <Stage
      step="1"
      title="What the model is told"
      note="Two halves, assembled per request. Nothing below this line is generated — it is the prompt that produced the section above."
    >
      <div className="wt-prompts">
        <details className="wt-fold" open>
          <summary>
            The standing instructions <span>{instructions.length.toLocaleString()} chars</span>
          </summary>
          <pre className="insp-json wt-tall">{instructions}</pre>
        </details>
        <details className="wt-fold">
          <summary>
            The document, appended for this request{' '}
            <span>{document.length.toLocaleString()} chars</span>
          </summary>
          <pre className="insp-json wt-tall">{document}</pre>
        </details>
      </div>
      <p className="wt-aside">
        Read it and you will notice what is <em>not</em> in it: no field names, no
        lengths, no list of allowed values. Those travel as{' '}
        <code>response_format={str(trace?.response_format) || 'SectionPlan'}</code> — a JSON
        Schema generated from the molecule union, which constrains generation itself. The prose
        says what to produce. The schema decides what can be produced at all.
      </p>
    </Stage>
  );
}

/** Stage 3. What the sanitiser did — usually, and importantly, nothing. */
function Repairs({ repairs }) {
  const changes = arr(repairs);

  if (changes.length === 0) {
    return (
      <p className="wt-clean">
        Nothing to repair on this run. The molecule validated and passed through untouched.
      </p>
    );
  }

  return (
    <table className="insp-map">
      <thead>
        <tr>
          <th>Field</th>
          <th>Returned</th>
          <th>Drawn</th>
        </tr>
      </thead>
      <tbody>
        {changes.map((change) => (
          <tr key={str(change?.field)}>
            <td>
              <code>{str(change?.field)}</code>
            </td>
            <td>
              <code className="wt-was">{str(change?.was)}</code>
            </td>
            <td>
              <code>{str(change?.now)}</code>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Stage 6. Every binding, and the value the binder pulls into it. */
function Resolved({ rows }) {
  return (
    <div className="insp-scroll">
      <table className="insp-map">
        <thead>
          <tr>
            <th>Prop</th>
            <th>Bound to</th>
            <th>Resolves to</th>
          </tr>
        </thead>
        <tbody>
          {arr(rows).map((row) => {
            const value = row?.value;
            const json = str(row?.json);
            return (
              <tr key={str(row?.path)}>
                <td>
                  <code>{str(row?.field)}</code>
                </td>
                <td>
                  <code>{str(row?.path)}</code>
                </td>
                <td className="wt-value">
                  {json ? (
                    <code>{json}</code>
                  ) : typeof value === 'boolean' ? (
                    <code>{String(value)}</code>
                  ) : (
                    str(value) || <span className="insp-dim">empty</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function Walkthrough({ trace, surfaces, isOpen, onToggle }) {
  const family = str(trace?.family);
  const component = str(trace?.component_name);
  const index = trace?.index;
  const surface = surfaces?.get(str(trace?.surface_id)) ?? null;

  return (
    <section className="walkthrough" aria-label="One molecule, traced from prompt to pixels">
      <button type="button" className="insp-toggle" onClick={onToggle} aria-expanded={isOpen}>
        <span className="small-label" style={{ margin: 0 }}>
          {isOpen ? '▾' : '▸'} Walkthrough — one molecule, prompt to pixels
        </span>
        <span className="insp-counts">
          {family ? (
            <>
              tracing <code>{family}</code> at index {index}
            </>
          ) : (
            'waiting for a run'
          )}
        </span>
      </button>

      {!isOpen ? null : !trace ? (
        <div className="wt-body">
          <p className="wt-note">
            Nothing traced yet. The walkthrough is built from a completed run — it appears once
            the section above finishes generating.
          </p>
        </div>
      ) : (
        <div className="wt-body">
          <p className="wt-intro">
            Six stages, in order, for one molecule of the section above — the{' '}
            <code>{family}</code> at index {index}. Every artifact below was produced by the run
            you just watched, not written out as an example, so each stage is checkable against
            the one before it.
          </p>

          <Prompt trace={trace} />

          <Stage
            step="2"
            title="What the model returns"
            note={`Structured output, validated against the molecule union. This is one molecule of the section; ${str(trace?.model)} produced it.`}
          >
            <pre className="insp-json">{pretty(trace?.returned)}</pre>
            <p className="wt-aside">
              <code>type</code> is the design decision, and it is the model's to make — it chose
              this family over the other four. What it did not write is anything below: no
              component name, no class, no colour, no path. Those do not appear in the schema, so
              they cannot appear in the answer.
            </p>
          </Stage>

          <Stage
            step="3"
            title="Repaired, or passed through"
            note="Validation guarantees the shape. This stage handles the states that are structurally legal but wrong on screen — a source line with no label above it, a band with nothing to open it."
          >
            <Repairs repairs={trace?.repairs} />
          </Stage>

          <Stage
            step="4"
            title="The values go into the data model"
            note="First A2UI message. The molecule's content is written to the surface's data model — and only its content: no markup, no component, nothing about how it looks."
          >
            <p className="insp-bind">
              <code>updateDataModel</code> → <code>{str(trace?.data_path)}</code>
            </p>
            <pre className="insp-json">{pretty(trace?.drawn)}</pre>
            <p className="wt-aside">
              The real message writes the whole model at <code>/</code> in one go; this is the
              slice of it that the bindings below resolve against.
            </p>
          </Stage>

          <Stage
            step="5"
            title="The component tree names no values"
            note="Second A2UI message, and the one worth pausing on."
          >
            <p className="insp-bind">
              <code>updateComponents</code> → <code>{family}</code> compiled to{' '}
              <code>{component}</code>
            </p>
            {/* Uncapped: the claim being made is about every path, so a pane that
                scrolls the last two out of sight undercuts it. */}
            <pre className="insp-json wt-full">{pretty(trace?.component)}</pre>
            <p className="wt-aside">
              Not one value in it. Every prop is a pointer into the data model, and the whole
              structure follows from <code>type</code> — the compiler derived the component name
              and all seven paths without making a single decision the model had not already made.
              That is what makes this stage mechanical, and why the model is not asked to write it.
            </p>
          </Stage>

          <Stage
            step="6"
            title="The binder resolves, the design system draws"
            note="A2UI's generic binder walks each pointer, pulls the value out of the data model, and hands the component already-resolved props. The molecule never sees a binding object."
          >
            <Resolved rows={trace?.resolved} />

            <p className="wt-drawn-label">
              And the pixels — drawn here by the same renderer and the same catalog as the section
              above, from its own surface:
            </p>
            <div className="wt-drawn">
              {surface ? (
                <A2uiSurface surface={surface} />
              ) : (
                <p className="wt-note">Surface not loaded.</p>
              )}
            </div>
            <p className="wt-aside">
              Every class, colour, weight and rule in what you just saw came from{' '}
              <code>signal.css</code>. The agent contributed the words and one family name.
              Change the tone from <code>{str(trace?.returned?.tone) || 'context'}</code> to
              something else and the line colour changes — because the stylesheet maps meaning to
              colour, and nothing in the chain above ever mentioned one.
            </p>
          </Stage>
        </div>
      )}
    </section>
  );
}
