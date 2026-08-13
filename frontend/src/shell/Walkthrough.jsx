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

/** A count off the wire, or zero. */
function numOf(value) {
  return Number.isFinite(value) ? value : 0;
}

/**
 * One stage.
 *
 * `change` states the transformation as a type signature. It is there because the
 * first question anyone asks of a six-stage diagram is what each stage actually
 * does to the thing passing through it — and two stages can produce
 * byte-identical output while doing entirely different work, which is precisely
 * the case between stages 2 and 4.
 */
function Stage({ step, title, change, note, children }) {
  return (
    <section className="wt-stage">
      <h4>
        <span className="insp-step">{step}</span>
        {title}
      </h4>
      {change ? <p className="wt-change">{change}</p> : null}
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
      change="prompt text + a JSON Schema → the request"
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

/**
 * Stage 3. The sanitiser, whose two outcomes are different in kind.
 *
 * A **repair** edits one field and the molecule still renders: a `source` with no
 * `label` above it would draw as an orphan line, so the source is cleared and the
 * band survives. A **drop** discards the whole molecule and it never reaches the
 * browser at all: a callout with neither `lead` nor `label` has nothing to open
 * it, a score table with a total but no rows has nothing for the total to line up
 * with. Presenting those as the same thing would be wrong.
 *
 * The drop count has to come from the run's totals, not from the traced molecule.
 * The trace can only ever follow a survivor — a dropped molecule is not in the
 * list to be chosen from — so reporting only what happened to this one would
 * silently assert that nothing was discarded.
 */
function Sanitiser({ trace }) {
  const changes = arr(trace?.repairs);
  const dropped = numOf(trace?.dropped_count);
  const returnedCount = numOf(trace?.returned_count);

  return (
    <>
      {changes.length === 0 ? (
        <p className="wt-clean">
          This molecule needed no repair — it passed through untouched.
        </p>
      ) : (
        <table className="insp-map">
          <thead>
            <tr>
              <th>Field repaired</th>
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
      )}

      {/* The run's totals, because the traced molecule cannot speak for them. */}
      <p className={dropped > 0 ? 'wt-dropped' : 'wt-clean'}>
        {dropped > 0 ? (
          <>
            Across the whole run, {dropped} of the {returnedCount} molecules the model returned
            were <strong>dropped</strong> rather than repaired — they never reached the browser.
            One unusable molecule costs itself, not the section.
          </>
        ) : (
          <>
            And none of the {returnedCount} molecules this run returned were dropped. A drop is
            the other outcome here, and it is not a repair: the molecule is discarded and never
            reaches the browser.
          </>
        )}
      </p>
    </>
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
          <p className="wt-intro">
            Each stage states what it does to the thing passing through it. Worth reading those
            lines first: two stages here produce almost identical JSON while doing completely
            different work, and the similarity is the system behaving correctly rather than a
            step repeating itself.
          </p>

          <Prompt trace={trace} />

          <Stage
            step="2"
            title="What the model returns"
            change={`JSON text → a validated ${component || 'molecule'} object, in server memory`}
            note={`Structured output, parsed and validated against the molecule union. This is one molecule of the section; ${str(trace?.model)} produced it. Nothing has left the server yet.`}
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
            title="Repaired, dropped, or passed through"
            change={`${component || 'Molecule'} → the same object, one field edited, or nothing at all`}
            note="Validation has already guaranteed the shape. What is left are the states that are structurally legal but wrong on screen — and they get one of two different treatments, which is the thing to be clear about here."
          >
            <Sanitiser trace={trace} />
            <p className="wt-aside">
              A <strong>repair</strong> edits one field and the molecule still draws: a{' '}
              <code>source</code> with no <code>label</code> above it would render as an orphan
              line, so the source is cleared and the band survives. A <strong>drop</strong>{' '}
              discards the molecule entirely — a callout with neither <code>lead</code> nor{' '}
              <code>label</code> has nothing to open it, a score table with a total but no rows
              has nothing for the total to line up with. Those never reach the browser.
            </p>
            <p className="wt-aside">
              Which is why the counts above are the run's and not this molecule's: the trace can
              only follow a molecule that survived, so it is not in a position to tell you about
              one that did not.
            </p>
          </Stage>

          <Stage
            step="4"
            title="The values cross the wire, addressed"
            change={`${component || 'Molecule'} → an A2UI updateDataModel message`}
            note="The first of the two protocol messages, shown whole. This is where the molecule stops being a server-side object and becomes addressable data inside a surface the browser owns."
          >
            <p className="insp-bind">
              <code>updateDataModel</code> → the whole model at <code>/</code>, traced molecule
              at <code>{str(trace?.data_path)}</code>
              {/* The pane scrolls: this is the real message, all
                  {' '}{numOf(trace?.drawn_count)} molecules of it. */}
              <span className="insp-dim">
                {' '}
                — all {numOf(trace?.drawn_count)} molecules, so the pane scrolls
              </span>
            </p>
            <pre className="insp-json wt-tall">{pretty(trace?.data_message)}</pre>
            <p className="wt-aside">
              Compare the values at <code>{str(trace?.data_path)}</code> against stage 2: they are
              identical, character for character. <em>That is the stage working, not a repeat of
              it.</em> Compiling adds an envelope, a surface id and an address — never content. If
              a value had changed here, the compiler would be editing the agent's analysis, which
              is exactly what it must not do.
            </p>
          </Stage>

          <Stage
            step="5"
            title="The component tree names no values"
            change={`the family name "${family}" → a ${component || 'component'} with ${arr(trace?.resolved).length} bindings`}
            note="The second protocol message. Only the traced molecule's component is shown; the real message carries one of these per molecule plus the root that stacks them."
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
            change="message + data model → resolved props → pixels"
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
