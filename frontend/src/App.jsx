import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';

import Header from './shell/Header.jsx';
import ProtocolInspector from './shell/ProtocolInspector.jsx';
import ReviewPane from './shell/ReviewPane.jsx';
import Section from './shell/Section.jsx';
import Timings from './shell/Timings.jsx';
import { INSPECT_ACTION, signalCatalog } from './a2ui/catalog.jsx';
import {
  SECTION_SURFACE_ID,
  deleteSurfaceMessage,
  transportFailureMessages,
} from './a2ui/messages.js';
import { fetchRfpHeader, streamInspect, streamOverview } from './lib/stream.js';

/**
 * The RFP page.
 *
 * The structure is fixed and hand-built — three numbered sections, the first
 * generated and the other two locked, exactly as the design mock has them. The
 * only thing the agent produces is the body of section 1, which arrives as A2UI
 * v0.9 messages and is drawn by A2UI's renderer against the catalog in
 * `a2ui/catalog.jsx`.
 *
 * The division of state is the thing to understand before editing. **Molecules
 * are not React state.** They live in the `MessageProcessor`'s surface data
 * model, which owns them and mutates in place. This component holds only the
 * chrome — the header, the subtitle, the counts, the timings, which datapoint is
 * being inspected — and a snapshot of *which surfaces exist* so React knows when
 * to mount a new one.
 *
 * Both streaming passes still run, and replace-wins is still load-bearing: the
 * optimistic pass sends `updateDataModel` + `updateComponents` per molecule as it
 * is parsed, and the authoritative pass re-sends the whole surface once the
 * generation is validated. A2UI addresses components by id, so the second pass
 * overwrites the first rather than appending to it.
 */

const LOCKED_SECTIONS = [
  { index: 2, title: 'Prospect Intelligence' },
  { index: 3, title: 'Suggested POVs' },
];

// A bound on the inspector's recording, so a long session cannot grow it without
// limit. A section run is ~15 frames; an inspect answer adds 3.
const MAX_FRAMES = 300;

export default function App() {
  const [rfp, setRfp] = useState(null);
  const [isStreaming, setIsStreaming] = useState(true);

  // Everything the section head and the timings readout need, merged as `meta`
  // frames arrive. Not A2UI — chrome is not a component.
  const [meta, setMeta] = useState(null);

  // A snapshot of the processor's surfaces. This is not mirrored state:
  // `processor.model.surfacesMap` is externally owned and mutated in place, so
  // React cannot observe it. Re-snapshotting on the processor's own
  // create/delete events is what makes a new surface mount.
  const [surfaces, setSurfaces] = useState(() => new Map());

  const [inspection, setInspection] = useState(null);
  const [isThinking, setIsThinking] = useState(false);
  const inspectAbort = useRef(null);

  // The inspector's record of the stream. Diagnostic only — nothing renders from
  // `frames` or `plan`, and deleting the inspector would leave the page identical.
  // That is the property the demo is meant to show.
  const [frames, setFrames] = useState([]);
  const [plan, setPlan] = useState(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const seqRef = useRef(0);

  const record = useCallback((channel, payload) => {
    seqRef.current += 1;
    // Date.now() outside the updater: an updater must stay pure, and React runs
    // it twice in development.
    const frame = { seq: seqRef.current, at: Date.now(), channel, payload };
    setFrames((previous) => (previous.length >= MAX_FRAMES ? previous : [...previous, frame]));
  }, []);

  // The action handler and `openInspection` each need the other. The ref breaks
  // the cycle without rebuilding the processor on every render, which would
  // discard every surface it holds.
  const openRef = useRef(null);

  const processor = useMemo(
    () =>
      new MessageProcessor([signalCatalog], (action) => {
        // The client-to-server half of A2UI. Every inspect target in every
        // molecule family comes through this one path, whichever tile was
        // clicked, because the subject travels in the action context.
        if (action.name !== INSPECT_ACTION) return;
        const subject = action.context?.subject;
        if (typeof subject === 'string' && subject) openRef.current?.(subject);
      }),
    [],
  );

  useEffect(() => {
    const sync = () => setSurfaces(new Map(processor.model.surfacesMap));
    const created = processor.onSurfaceCreated(sync);
    const deleted = processor.onSurfaceDeleted(sync);
    sync();
    return () => {
      created.unsubscribe();
      deleted.unsubscribe();
    };
  }, [processor]);

  useEffect(() => {
    const controller = new AbortController();

    fetchRfpHeader(controller.signal).then((header) => {
      if (!controller.signal.aborted) setRfp(header);
    });

    const handleEvent = (name, payload) => {
      if (controller.signal.aborted) return;
      record(name, payload);

      if (name === 'a2ui') {
        try {
          processor.processMessages([payload]);
        } catch (error) {
          // A message the renderer rejects is a bug on our side of the
          // protocol, not something to show the user: the authoritative pass
          // re-sends the whole surface a moment later.
          console.error('A2UI message rejected', error);
        }
        return;
      }

      // The model's structured output. Held for the inspector and nothing else —
      // the page above is drawn entirely from the `a2ui` channel.
      if (name === 'plan') {
        setPlan(payload);
        return;
      }

      if (name === 'meta') {
        setMeta((previous) => ({ ...previous, ...payload }));
      }
    };

    streamOverview(handleEvent, controller.signal)
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('overview stream failed', error);
        // The backend reports its own failures as a risk band on the surface;
        // this path is the transport itself breaking, which it cannot report.
        processor.processMessages(
          transportFailureMessages(processor.model.surfacesMap.has(SECTION_SURFACE_ID)),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsStreaming(false);
      });

    return () => controller.abort();
  }, [processor, record]);

  const openInspection = useCallback((subject) => {
    setInspection({ subject, turns: [] });
  }, []);

  // Published for the processor's action handler. In an effect rather than
  // during render, because assigning a ref while rendering is a side effect.
  useEffect(() => {
    openRef.current = openInspection;
  }, [openInspection]);

  const closeInspection = useCallback(() => {
    inspectAbort.current?.abort();

    // An answer can attach its own surface. Dropping the turns without deleting
    // them would leak one surface per question asked. Done here rather than in
    // the state updater — an updater must be pure, and React runs it twice in
    // development.
    for (const turn of inspection?.turns ?? []) {
      if (turn.surfaceId) processor.processMessages([deleteSurfaceMessage(turn.surfaceId)]);
    }

    setInspection(null);
    setIsThinking(false);
  }, [inspection, processor]);

  /**
   * Append an assistant turn to whichever inspection is still open.
   *
   * Guarded on subject: if the user closed the pane and clicked a different
   * datapoint while an answer was in flight, that answer belongs to the old
   * subject and must not be appended under the new one.
   */
  const appendAnswer = useCallback((subject, turn) => {
    setInspection((current) =>
      current && current.subject === subject
        ? { ...current, turns: [...current.turns, turn] }
        : current,
    );
  }, []);

  const ask = useCallback(
    (question) => {
      if (!inspection) return;
      const { subject, turns } = inspection;

      // The request is started here rather than inside a state updater — an
      // updater must be pure, and React invokes it twice in development, which
      // would fire two requests per question.
      const controller = new AbortController();
      inspectAbort.current = controller;
      setIsThinking(true);
      setInspection({ ...inspection, turns: [...turns, { role: 'user', content: question }] });

      // History is prior turns only. The current question travels in `question`,
      // and sending it in both places makes the model answer it as though it had
      // already been asked once.
      const history = turns.map((turn) => ({ role: turn.role, content: turn.content }));

      streamInspect(
        { question, subject, history },
        (name, payload) => {
          if (controller.signal.aborted) return;
          record(name, payload);

          // Molecules attached to an answer arrive as their own surface, sent
          // ahead of the answer that names it.
          if (name === 'a2ui') {
            try {
              processor.processMessages([payload]);
            } catch (error) {
              console.error('A2UI message rejected', error);
            }
            return;
          }

          if (name !== 'answer') return;
          appendAnswer(subject, {
            role: 'assistant',
            content: payload.answer,
            surfaceId: typeof payload.surface_id === 'string' ? payload.surface_id : null,
          });
        },
        controller.signal,
      )
        .catch((error) => {
          if (error.name === 'AbortError') return;
          console.error('inspect stream failed', error);
          appendAnswer(subject, {
            role: 'assistant',
            content: 'That question could not be answered. Try again.',
            surfaceId: null,
          });
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsThinking(false);
        });
    },
    [appendAnswer, inspection, processor, record],
  );

  const sectionSurface = surfaces.get(SECTION_SURFACE_ID) ?? null;
  const isPaneOpen = Boolean(inspection);

  return (
    <main className={isPaneOpen ? 'layout-two-col active' : 'layout-two-col'}>
      <div className="left-col">
        <Header rfp={rfp} />

        <Section
          index={1}
          title="RFP Overview"
          summary={meta?.summary ?? ''}
          surface={sectionSurface}
          moleculeCount={meta?.molecule_count ?? 0}
          signalCount={meta?.signal_count ?? 0}
          isStreaming={isStreaming}
          cta={
            // No literal arrow in the label: the DS puts one on `.cta-button`
            // via `::after`, and adding our own renders "→ →".
            <div className="section-cta">
              <button type="button" className="cta-button">
                Continue to Prospect Intelligence
              </button>
            </div>
          }
        />

        {LOCKED_SECTIONS.map((section) => (
          <Section key={section.index} index={section.index} title={section.title} isLocked />
        ))}

        <Timings timings={meta} moleculeCount={meta?.molecule_count ?? 0} />

        <ProtocolInspector
          plan={plan}
          frames={frames}
          surfaceId={SECTION_SURFACE_ID}
          isOpen={isInspectorOpen}
          onToggle={() => setIsInspectorOpen((open) => !open)}
        />
      </div>

      {isPaneOpen ? (
        <ReviewPane
          subject={inspection.subject}
          turns={inspection.turns}
          surfaces={surfaces}
          isThinking={isThinking}
          onAsk={ask}
          onClose={closeInspection}
        />
      ) : null}
    </main>
  );
}
