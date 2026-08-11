import { useCallback, useEffect, useRef, useState } from 'react';
import Header from './shell/Header.jsx';
import ReviewPane from './shell/ReviewPane.jsx';
import Section from './shell/Section.jsx';
import Timings from './shell/Timings.jsx';
import { fetchRfpHeader, streamInspect, streamOverview } from './lib/stream.js';

/**
 * The RFP page.
 *
 * The structure is fixed and hand-built — three numbered sections, the first
 * generated and the other two locked, exactly as the design mock has them. The
 * only thing the agent produces is the body of section 1, and it arrives one
 * molecule at a time.
 *
 * Molecule state has two writers, which is worth understanding before editing:
 * the optimistic stream appends at an index, and the authoritative `section` event
 * replaces the whole list. Replace-wins is what lets the second pass silently fix
 * anything the first pass got wrong.
 */

const LOCKED_SECTIONS = [
  { index: 2, title: 'Prospect Intelligence' },
  { index: 3, title: 'Suggested POVs' },
];

export default function App() {
  const [rfp, setRfp] = useState(null);
  const [summary, setSummary] = useState('');
  const [molecules, setMolecules] = useState([]);
  const [isStreaming, setIsStreaming] = useState(true);
  const [timings, setTimings] = useState(null);

  const [inspection, setInspection] = useState(null);
  const [isThinking, setIsThinking] = useState(false);
  const inspectAbort = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchRfpHeader(controller.signal).then((header) => {
      if (!controller.signal.aborted) setRfp(header);
    });

    const handleEvent = (name, payload) => {
      if (controller.signal.aborted) return;

      if (name === 'molecule') {
        // Append at the index the agent gave, rather than pushing, so an
        // out-of-order or duplicated frame lands in one place instead of
        // producing two copies of the same band.
        setMolecules((previous) => {
          const next = previous.slice();
          next[payload.index] = payload.molecule;
          return next;
        });
        return;
      }

      if (name === 'section') {
        setSummary(payload.summary ?? '');
        setMolecules(payload.molecules ?? []);
        return;
      }

      if (name === 'meta') {
        setTimings(payload);
      }
    };

    streamOverview(handleEvent, controller.signal)
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('overview stream failed', error);
        // The backend yields a renderable fallback for its own failures; this
        // path is the transport itself breaking, which it cannot report.
        setMolecules([
          {
            type: 'callout',
            tone: 'risk',
            lead: 'Lost the connection.',
            body: 'The section stopped streaming before it finished. Reload to try again.',
          },
        ]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsStreaming(false);
      });

    return () => controller.abort();
  }, []);

  const openInspection = useCallback((subject) => {
    setInspection({ subject, turns: [] });
  }, []);

  const closeInspection = useCallback(() => {
    inspectAbort.current?.abort();
    setInspection(null);
    setIsThinking(false);
  }, []);

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
          if (name !== 'answer' || controller.signal.aborted) return;
          appendAnswer(subject, {
            role: 'assistant',
            content: payload.answer,
            molecules: payload.molecules ?? [],
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
            molecules: [],
          });
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsThinking(false);
        });
    },
    [appendAnswer, inspection],
  );

  const signalCount = molecules.filter((molecule) => molecule?.signal).length;
  const isPaneOpen = Boolean(inspection);

  return (
    <main className={isPaneOpen ? 'layout-two-col active' : 'layout-two-col'}>
      <div className="left-col">
        <Header rfp={rfp} />

        <Section
          index={1}
          title="RFP Overview"
          summary={summary}
          molecules={molecules}
          signalCount={signalCount}
          isStreaming={isStreaming}
          onInspect={openInspection}
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

        <Timings timings={timings} moleculeCount={molecules.length} />
      </div>

      {isPaneOpen ? (
        <ReviewPane
          subject={inspection.subject}
          turns={inspection.turns}
          isThinking={isThinking}
          onAsk={ask}
          onClose={closeInspection}
        />
      ) : null}
    </main>
  );
}
