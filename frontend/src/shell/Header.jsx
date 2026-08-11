/**
 * The page chrome: nav and the RFP header card.
 *
 * Nothing here is generated, and that is the point. The title, client, sector and
 * reference come from the record; the model never gets to invent which RFP you are
 * looking at. Keeping the chrome in its own static component makes the boundary
 * between "the product" and "the generated section" visible in the file tree.
 */
export default function Header({ rfp }) {
  return (
    <>
      <nav className="top-nav">
        <div className="brand">
          signal<strong>78</strong>
        </div>
        <div className="nav-items">
          <span className="nav-item active">RFPs</span>
        </div>
      </nav>

      <header className="glass" style={{ padding: 'var(--s-7)' }}>
        <div style={{ position: 'relative', zIndex: 2 }}>
          <div className="small-label" style={{ marginBottom: 'var(--s-3)' }}>
            ← All RFPs
          </div>
          <h1 style={{ fontSize: 34, fontWeight: 500, lineHeight: 1.2 }}>
            {rfp?.title ?? 'Loading RFP…'}
          </h1>
          {rfp ? (
            <div className="subtitle" style={{ marginTop: 6 }}>
              {rfp.client} · {rfp.sector} · {rfp.reference}
            </div>
          ) : null}
        </div>
      </header>
    </>
  );
}
