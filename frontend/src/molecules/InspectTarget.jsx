/**
 * Makes a design-system block behave like a button without being one.
 *
 * Why not a real `<button>`: the design system's inspect affordance is applied
 * to `<div>`s — all 21 inspect targets in the DS export are divs, and the
 * stylesheet carries no button reset. Wrapping a `.callout` or `.score-row` in a
 * `<button>` inherits UA styling (centred text, system font, its own border) and
 * visibly breaks the band, and the row grids that DS §3.3 says to keep.
 *
 * So the markup stays as the DS ships it and the semantics are added here, in one
 * place, rather than three times across the molecules. This is a real gap in the
 * exported design system, not a preference: as authored, every inspect target in
 * the product is unreachable by keyboard and invisible to a screen reader. The
 * production fix belongs in the DS — either a button reset or ARIA in the spec.
 */
export default function InspectTarget({ className, label, onInspect, children }) {
  if (!onInspect) {
    return <div className={className}>{children}</div>;
  }

  const activate = () => onInspect(label);

  return (
    <div
      className={className}
      role="button"
      tabIndex={0}
      aria-label={`Inspect: ${label}`}
      onClick={activate}
      onKeyDown={(event) => {
        // Space and Enter are what a real button answers to; Space must not also
        // scroll the page.
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          activate();
        }
      }}
    >
      {children}
    </div>
  );
}
