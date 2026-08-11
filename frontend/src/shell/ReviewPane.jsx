import { useState } from 'react';
import Molecule from '../molecules/registry.jsx';

/**
 * DS §4.3/§4.4 — the inspect sidebar and its feedback loop.
 *
 * This is the only chat in the product, and it is deliberately small: it is scoped
 * to the one datapoint the user clicked, not to the page. The subject line at the
 * top is what makes that scope legible — you are asking about *this*, and the
 * agent is answering about *this*.
 *
 * The reply can carry molecules of its own, rendered through the same registry as
 * the section, so an answer about a source arrives as a real intel card rather than
 * a paragraph describing one.
 */
export default function ReviewPane({ subject, turns, isThinking, onAsk, onClose }) {
  const [draft, setDraft] = useState('');

  const submit = (event) => {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isThinking) return;
    setDraft('');
    onAsk(question);
  };

  return (
    <aside className="response-pane">
      <div className="card-arrow" />
      <div className="card-dark viewed">
        <button type="button" className="card-close" onClick={onClose} aria-label="Close review">
          ×
        </button>

        <div className="small-label" style={{ color: 'var(--positive)' }}>
          ✦ Signal Review Agent
        </div>

        <p className="card-text">
          <span className="card-indicator" />
          {subject}
        </p>

        <div className="card-conversation">
          {turns.length === 0 && !isThinking ? (
            <div className="conv-section">
              <span className="conv-label">Signal Review</span>
              <div className="conv-ai">
                Ask me about this — where it is sourced, why it is flagged — or leave a
                comment and I will carry it into the brief.
              </div>
            </div>
          ) : null}

          {turns.map((turn, index) => (
            <div className="conv-section" key={index}>
              <span className="conv-label">{turn.role === 'user' ? 'You' : 'Signal Review'}</span>
              {turn.role === 'user' ? (
                <div className="conv-user">{turn.content}</div>
              ) : (
                <>
                  <div className="conv-ai">{turn.content}</div>
                  {turn.molecules?.length ? (
                    <div className="pane-molecules">
                      {turn.molecules.map((molecule, position) => (
                        <Molecule key={position} molecule={molecule} />
                      ))}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ))}

          <div role="status" aria-live="polite">
            {isThinking ? <div className="conv-confirm">Reading the document…</div> : null}
          </div>
        </div>

        <form className="card-feedback" onSubmit={submit}>
          <label className="fb-label" htmlFor="review-input">
            Message Signal Review
          </label>
          <textarea
            id="review-input"
            className="fb-input"
            value={draft}
            placeholder="Ask about this insight, or add context the brain should know…"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              // Enter sends, Shift+Enter makes a new line — the convention for a
              // single-purpose composer like this one.
              if (event.key === 'Enter' && !event.shiftKey) submit(event);
            }}
          />
          <div className="fb-actions">
            <button type="submit" className="fb-submit" disabled={isThinking}>
              Send
            </button>
          </div>
        </form>
      </div>
    </aside>
  );
}
