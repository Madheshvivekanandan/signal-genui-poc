/**
 * Why the model does not write A2UI itself.
 *
 * The first question anyone asks about this POC once they understand the
 * compiler is: A2UI is designed for LLMs to emit these messages directly, so why
 * is there a translation step? It is a fair question with a real answer, and the
 * answer is an architectural trade rather than a rule — so this panel argues both
 * sides and then commits.
 *
 * The number in the middle is measured, not written. `a2ui.directness_cost()`
 * compiles the molecules the agent returned for the document currently on screen
 * and reports what the model would have had to emit had it written the protocol
 * itself. Switch documents and it changes. That matters because the claim being
 * made — that the compiled part carries no decisions — is only worth anything if
 * it is checkable.
 *
 * Reference material about the system, like `MoleculeCatalog`, so it sits below
 * it and collapses by default.
 */

/** A count from the wire, or zero. The meta channel is JSON from our own server,
    but this panel is chrome and must not throw on a partial frame. */
function num(value) {
  return Number.isFinite(value) ? value : 0;
}

/** The two arguments, each stated as strongly as it deserves. */
const CASES = [
  {
    id: 'direct',
    name: 'The model writes A2UI',
    note: "A2UI's documented default",
    pros: [
      'Canonical usage. The protocol was shaped for it — a flat component list with id references is easy for a model to generate incrementally and to correct mid-stream.',
      'No compiler to own. The backend relays; a component is added in one place instead of three.',
      'Genuinely open-ended. The model can compose a layout nobody anticipated out of Column, Row and Card.',
    ],
    cons: [
      'More to generate, all of it derivable. The component tree carries no information that `type` did not already imply.',
      'Weaker guarantees at decode time. A closed molecule union is a schema the API can constrain against; the full message union with arbitrary component props is much harder to, so validation moves to runtime.',
      'Ordering becomes the model’s problem. Data must be written before the components that bind to it, and nothing stops a model emitting them the other way round.',
      'The catalog rejects an invented component name. It does not reject a binding path with a typo in it — that prop silently renders nothing.',
    ],
  },
  {
    id: 'compiled',
    name: 'The model writes molecules',
    note: 'what this POC does',
    pros: [
      'The model emits decisions and nothing else. Which family a statement becomes is its call; the markup that follows from that is not a second decision.',
      'Invalid output is undecodable rather than caught late — structured outputs constrain generation against the union itself.',
      'Streaming gets simpler. A molecule is self-contained, so one can be drawn the instant it is provably complete.',
      'Repairs can be semantic. The sanitiser works on meaning — a source with no label, a callout with no lead — which is not visible in a component tree.',
      'Layout stays in the design system, which is the premise the whole POC rests on.',
    ],
    cons: [
      'A real compiler to maintain, and two closed sets that have to stay in step.',
      'Adding a family is three coupled edits: the union, the view table, the frontend catalog.',
      'The model cannot reach for a layout you did not anticipate. Out of vocabulary is out of reach.',
    ],
  },
];

function Case({ block }) {
  return (
    <section className="choice-case">
      <h4>
        {block.name}
        <em>{block.note}</em>
      </h4>
      <p className="choice-side">For</p>
      <ul className="choice-pros">
        {block.pros.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p className="choice-side">Against</p>
      <ul className="choice-cons">
        {block.cons.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The measurement, for the document on screen.
 *
 * Renders nothing at all until the authoritative pass has landed — a ratio built
 * from a half-streamed section would be wrong in a way nobody would notice.
 */
function Measured({ cost }) {
  const typed = num(cost?.typed_bytes);
  const direct = num(cost?.direct_bytes);
  if (!typed || !direct) return null;

  const ratio = (direct / typed).toFixed(2);

  return (
    <div className="choice-measure">
      <div className="choice-figure">
        <strong>{ratio}×</strong>
        <span>
          the output, for the same pixels — measured on the document above, not
          quoted from a benchmark
        </span>
      </div>
      <table className="choice-numbers">
        <tbody>
          <tr>
            <th>Molecules the model emitted</th>
            <td>{typed.toLocaleString()} bytes</td>
          </tr>
          <tr>
            <th>The same, as A2UI it wrote itself</th>
            <td>{direct.toLocaleString()} bytes</td>
          </tr>
          <tr>
            <th>Compiled on its behalf</th>
            <td>
              {num(cost?.components).toLocaleString()} components ·{' '}
              {num(cost?.bindings).toLocaleString()} binding paths
            </td>
          </tr>
        </tbody>
      </table>
      <p className="choice-caption">
        Both figures cover the same data model; the difference is exactly the component tree.
        Every one of those binding paths is <code>/molecules/&lt;i&gt;/&lt;field&gt;</code> — fully
        determined by the family the model already named, and each one a chance to write a path
        that resolves to nothing.
      </p>
    </div>
  );
}

export default function ProtocolChoice({ cost, isOpen, onToggle }) {
  return (
    <section className="choice" aria-label="Why the agent does not emit A2UI directly">
      <button type="button" className="insp-toggle" onClick={onToggle} aria-expanded={isOpen}>
        <span className="small-label" style={{ margin: 0 }}>
          {isOpen ? '▾' : '▸'} Why the agent does not write A2UI itself
        </span>
        <span className="insp-counts">two valid designs · one chosen</span>
      </button>

      {isOpen ? (
        <div className="choice-body">
          <p className="choice-intro">
            A2UI is designed for models to generate its messages directly, and that is how its
            documentation leads. Composing them server-side is an equally supported pattern — the
            same protocol reaches the browser either way, and the renderer cannot tell which
            produced it. So this is not a question of conformance. It is a question of{' '}
            <strong>where the interface decision is made</strong>, and it is worth being able to
            defend either answer.
          </p>

          <Measured cost={cost} />

          <div className="choice-cases">
            {CASES.map((block) => (
              <Case key={block.id} block={block} />
            ))}
          </div>

          <div className="choice-verdict">
            <h4>Why this one</h4>
            <p>
              Two reasons, both specific to this product rather than general preference.
            </p>
            <p>
              <strong>The premise depends on it.</strong> What is being demonstrated is that the
              design system owns markup, colour, grid and type scale while the agent owns meaning.
              The moment the model chooses column widths, layout has left the stylesheet and moved
              into model output — and the thing on screen is no longer a bounded design system. It
              is a model writing CSS by proxy.
            </p>
            <p>
              <strong>And it is worse on the question this POC exists to answer.</strong> Whether
              generated UI feels immediate is the headline. Directness costs measurably more output
              for identical pixels, paid on the critical path to first paint, in exchange for work
              the model contributes no judgement to.
            </p>
            <p className="choice-flip">
              <strong>When the answer flips.</strong> If the product became open-ended — an agent
              composing screens nobody designed in advance, or surfaces beyond one fixed page —
              the vocabulary becomes a cage and the view table becomes the bottleneck. Direct
              generation is clearly right there. That is a different product from this one.
            </p>
          </div>

          <p className="choice-foot">
            Sources:{' '}
            <a href="https://a2ui.org/introduction/what-is-a2ui/" target="_blank" rel="noreferrer">
              a2ui.org — What is A2UI
            </a>{' '}
            ·{' '}
            <a
              href="https://developers.googleblog.com/introducing-a2ui-an-open-project-for-agent-driven-interfaces/"
              target="_blank"
              rel="noreferrer"
            >
              Google Developers Blog — Introducing A2UI
            </a>
          </p>
        </div>
      ) : null}
    </section>
  );
}
