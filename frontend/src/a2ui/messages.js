/**
 * The handful of A2UI messages the client builds for itself.
 *
 * Almost every message comes from the server; these two cases cannot. A dropped
 * connection is by definition something the backend could not report, and
 * closing the review pane is a user action with no server involvement — A2UI's
 * `deleteSurface` exists precisely so the client owns that one.
 */

import { CATALOG_ID } from './catalog.jsx';

export const VERSION = 'v0.9';

/** Must match `SECTION_SURFACE_ID` in `backend/a2ui.py`. */
export const SECTION_SURFACE_ID = 'rfp-overview';

/**
 * The band shown when the stream dies mid-flight.
 *
 * Built with inline values rather than data-model bindings: there is no second
 * update coming that could change this text, so a binding would add a data model
 * to maintain for no benefit. A2UI accepts a literal wherever it accepts a
 * `{path: …}`.
 *
 * `hasSurface` decides whether to open one first. The backend opens the section
 * surface as its very first act, so by the time a transport error is plausible it
 * usually exists — but a connection that failed before the first frame leaves
 * nothing to write into, and a `createSurface` for an id that already exists is
 * not a question worth making the renderer answer.
 */
export function transportFailureMessages(hasSurface) {
  const open = {
    version: VERSION,
    createSurface: { surfaceId: SECTION_SURFACE_ID, catalogId: CATALOG_ID },
  };

  const draw = {
    version: VERSION,
    updateComponents: {
      surfaceId: SECTION_SURFACE_ID,
      components: [
        {
          id: 'm0',
          component: 'Callout',
          tone: 'risk',
          lead: 'Lost the connection.',
          body: 'The section stopped streaming before it finished. Reload to try again.',
          inspect: false,
          signal: false,
        },
        { id: 'root', component: 'MoleculeStack', children: ['m0'] },
      ],
    },
  };

  return hasSurface ? [draw] : [open, draw];
}

/** Close a surface. The only message the client sends that the server never does. */
export function deleteSurfaceMessage(surfaceId) {
  return { version: VERSION, deleteSurface: { surfaceId } };
}
