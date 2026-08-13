/**
 * The protocol inspector — a demo surface, not a product one.
 *
 * It answers the question the architecture actually turns on: *what did the model
 * return, and what did A2UI make of it?* Three stages, in order:
 *
 *   1. Agent output — the model's structured JSON, exactly as it came back.
 *   2. The compile — each molecule mapped to the A2UI component and the data-model
 *      paths it binds. This is the step people assume is magic.
 *   3. The stream — every frame, in arrival order, with its channel.
 *   4. Measured — what the three stages above cost in wall-clock time.
 *
 * The fifth stage is the page above it, which is drawn *only* from stage 3.
 * Nothing here renders anything: if the inspector were deleted the UI would be
 * identical, and that is the point being demonstrated.
 */

import { useMemo } from 'react';

import Timings from './Timings.jsx';

/** A2UI v0.9's four server-to-client message types, in spec order. */
const MESSAGE_KINDS = ['createSurface', 'updateDataModel', 'updateComponents', 'deleteSurface'];

function messageKind(message) {
  return MESSAGE_KINDS.find((kind) => kind in message) ?? 'unknown';
}

/** A one-line gist, so the timeline is readable without expanding every frame. */
function summarise(frame) {
  if (frame.channel !== 'a2ui') {
    const keys = Object.keys(frame.payload ?? {});
    return keys.length ? keys.join(', ') : '—';
  }

  const kind = messageKind(frame.payload);
  const body = frame.payload[kind] ?? {};

  if (kind === 'createSurface') return `surface "${body.surfaceId}"`;
  if (kind === 'deleteSurface') return `surface "${body.surfaceId}" closed`;
  if (kind === 'updateComponents') {
    return (body.components ?? []).map((component) => component.id).join(', ') || '—';
  }
  if (kind === 'updateDataModel') {
    const molecules = body.value?.molecules;
    const count = Array.isArray(molecules) ? molecules.length : 0;
    return `${body.path} · ${count} molecule${count === 1 ? '' : 's'}`;
  }
  return '—';
}

/** The `{path: …}` props on one component definition, as readable pairs. */
function bindingsOf(component) {
  return Object.entries(component)
    .filter(([, value]) => value && typeof value === 'object' && typeof value.path === 'string')
    .map(([prop, value]) => ({ prop, path: value.path }));
}

/**
 * The last full component tree sent for a surface.
 *
 * The last `updateComponents` wins because the authoritative pass re-sends
 * everything — which is exactly the replace-wins behaviour worth showing.
 */
function latestTree(frames, surfaceId) {
  let tree = null;
  for (const frame of frames) {
    if (frame.channel !== 'a2ui') continue;
    const update = frame.payload.updateComponents;
    if (update?.surfaceId === surfaceId) tree = update.components;
  }
  return tree;
}

function Json({ value }) {
  return <pre className="insp-json">{JSON.stringify(value, null, 2)}</pre>;
}

export default function ProtocolInspector({
  plan,
  frames,
  surfaceId,
  timings,
  moleculeCount,
  isOpen,
  onToggle,
}) {
  const tree = useMemo(() => latestTree(frames, surfaceId), [frames, surfaceId]);
  const a2uiCount = frames.filter((frame) => frame.channel === 'a2ui').length;
  const returned = plan?.molecules ?? [];
  const rendered = (tree ?? []).filter((component) => component.id !== 'root');
  const t0 = frames.length ? frames[0].at : 0;

  return (
    <section className="inspector" aria-label="Protocol inspector">
      <button
        type="button"
        className="insp-toggle"
        onClick={onToggle}
        aria-expanded={isOpen}
      >
        <span className="small-label" style={{ margin: 0 }}>
          {isOpen ? '▾' : '▸'} Protocol inspector
        </span>
        <span className="insp-counts">
          {returned.length} molecules returned · {rendered.length} components ·{' '}
          {a2uiCount} A2UI messages
        </span>
      </button>

      {isOpen ? (
        <div className="insp-body">
          <div className="insp-stage">
            <h4>
              <span className="insp-step">1</span> Agent output
              <em>what the model returned — plain JSON, no UI in it</em>
            </h4>
            {plan ? (
              <>
                <p className="insp-note">
                  Model <code>{plan.model}</code>. Structured output validated against the{' '}
                  <code>Molecule</code> union. Choosing the family is the agent&rsquo;s call —{' '}
                  <code>type</code> is its design decision. What it never names is the A2UI
                  component that draws it, the paths it binds, or a colour. Stage 2 is where
                  those are decided.
                </p>
                <Json value={{ summary: plan.summary, molecules: plan.molecules }} />
              </>
            ) : (
              <p className="insp-note">Waiting for the agent to finish…</p>
            )}
          </div>

          <div className="insp-stage">
            <h4>
              <span className="insp-step">2</span> The compile
              <em>molecule → A2UI component + bindings</em>
            </h4>
            {rendered.length ? (
              <div className="insp-scroll">
                <table className="insp-map">
                  <thead>
                    <tr>
                      <th>Molecule</th>
                      <th>A2UI component</th>
                      <th>Bindings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rendered.map((component, index) => (
                      <tr key={component.id}>
                        <td>
                          <code>{returned[index]?.type ?? '—'}</code>
                          <span className="insp-dim"> [{index}]</span>
                        </td>
                        <td>
                          <code>{component.component}</code>
                          <span className="insp-dim"> id={component.id}</span>
                        </td>
                        <td>
                          {bindingsOf(component).map((binding) => (
                            <div key={binding.prop} className="insp-bind">
                              <code>{binding.prop}</code> → <code>{binding.path}</code>
                            </div>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="insp-note">No component tree yet.</p>
            )}
            {plan && returned.length !== rendered.length ? (
              <p className="insp-note insp-warn">
                {returned.length - rendered.length} molecule(s) the model returned were dropped as
                unrenderable and never reached the surface.
              </p>
            ) : null}
          </div>

          <div className="insp-stage insp-stage-wide">
            <h4>
              <span className="insp-step">3</span> The stream
              <em>{frames.length} frames, in arrival order</em>
            </h4>
            <ol className="insp-frames">
              {frames.map((frame) => (
                <li key={frame.seq}>
                  <div className="insp-frame-head">
                    <span className={`insp-chan insp-chan-${frame.channel}`}>{frame.channel}</span>
                    {frame.channel === 'a2ui' ? (
                      <code className="insp-kind">{messageKind(frame.payload)}</code>
                    ) : null}
                    <span className="insp-dim">+{frame.at - t0} ms</span>
                    <span className="insp-gist">{summarise(frame)}</span>
                  </div>
                  <details>
                    <summary>raw</summary>
                    <Json value={frame.payload} />
                  </details>
                </li>
              ))}
            </ol>
          </div>

          <div className="insp-stage insp-stage-wide">
            <h4>
              <span className="insp-step">4</span> Measured
              <em>what the three stages above cost</em>
            </h4>
            {timings?.total_ms != null ? (
              <Timings timings={timings} moleculeCount={moleculeCount} />
            ) : (
              <p className="insp-note">No completed run to measure yet.</p>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
