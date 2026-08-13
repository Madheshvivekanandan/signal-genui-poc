/**
 * The Signal A2UI catalog — the whitelist of what an agent can put on screen.
 *
 * This replaces the old `molecules/registry.jsx` dispatch. The security boundary
 * is the same idea and a stronger version of it: a component name the agent
 * invents is rejected by A2UI's renderer before it reaches any code of ours,
 * rather than by a `hasOwnProperty` check we have to remember to write.
 *
 * Each component is declared twice, by design: a Zod schema describing what may
 * be set and which props accept a `{path: …}` binding, and a React
 * implementation that receives already-resolved values. A2UI's generic binder
 * sits between them, so the molecules never see a binding object.
 *
 * Six components, and deliberately no more. **A2UI's basic catalog is not
 * registered** — `Column`, `Row` and `Card` inject their own flex styles and
 * spacing variables, which would compete with `signal.css` for control of the
 * section body. The only structural component here is `MoleculeStack`, which
 * draws the DS's own `.molecule-stack` and nothing else. A consequence worth
 * knowing: none of A2UI's stylesheets are imported, so there is no cascade to
 * reconcile.
 *
 * `CATALOG_ID` must match `CATALOG_ID` in `backend/a2ui.py`. It is an
 * identifier, never fetched.
 *
 * Note on `zod`: the binder classifies props by reading Zod 3 internals
 * (`_def.typeName`). Zod 4 renamed those, and the failure mode is silent —
 * every prop degrades to `STATIC` and bindings render as `[object Object]`.
 * Keep the dependency on `zod@^3`.
 */

import { Fragment } from 'react';
import { basicCatalog, createComponentImplementation } from '@a2ui/react/v0_9';
import { Catalog, CommonSchemas } from '@a2ui/web_core/v0_9';
import { z } from 'zod';

import ArcBeats from '../molecules/ArcBeats.jsx';
import Callout from '../molecules/Callout.jsx';
import ErrorBoundary from '../components/ErrorBoundary.jsx';
import MetricGrid from '../molecules/MetricGrid.jsx';
import PhasePlan from '../molecules/PhasePlan.jsx';
import ScoreTable from '../molecules/ScoreTable.jsx';

export const CATALOG_ID = 'https://signal.rfp/catalogs/rfp-overview/v1.json';

/** The one action the client sends back. Matches `INSPECT_ACTION` in the backend. */
export const INSPECT_ACTION = 'inspect';

const { ChildList, DynamicBoolean, DynamicString, DynamicValue } = CommonSchemas;

// Every prop is optional. The data model is written by an agent and can be
// mid-stream when a component first renders, so a missing prop must not be a
// schema violation — the molecules already degrade to nothing rather than throw.
const dynamicString = DynamicString.optional();
const dynamicFlag = DynamicBoolean.optional();
const dynamicValue = DynamicValue.optional();

// DS §3: every molecule can wear `.inspect` and `.signal`, so every family
// declares them. They are the agent's, not the renderer's.
const CAPABILITIES = { inspect: dynamicFlag, signal: dynamicFlag };

/**
 * Adapt an A2UI component context to the `onInspect(subject)` callback the
 * molecules already take.
 *
 * This is a real A2UI action, not a React side channel: it goes through
 * `dispatchAction`, arrives at the `MessageProcessor`'s handler in `App.jsx`,
 * and carries the datapoint's identity in the action context.
 *
 * It is dispatched from here rather than declared as an `action` prop on the
 * component because the subject is only known at click time — a metric grid has
 * four independently inspectable tiles, and a prop-declared action would fix one
 * context for the whole molecule.
 */
function inspectHandler(context) {
  return (subject) =>
    context.dispatchAction({ event: { name: INSPECT_ACTION, context: { subject } } });
}

/**
 * The section body's root: the DS's molecule stack.
 *
 * `children` is A2UI's `ChildList`. Our compiler always sends a plain array of
 * component ids, which the binder passes through untouched; the array check is
 * for the template form (`{componentId, path}`), which we never emit and must
 * not crash on.
 */
const MoleculeStackApi = {
  name: 'MoleculeStack',
  schema: z.object({ children: ChildList.optional() }),
};

const MoleculeStack = createComponentImplementation(MoleculeStackApi, ({ props, buildChild }) => (
  <div className="molecule-stack">
    {(Array.isArray(props.children) ? props.children : []).map((id) =>
      typeof id === 'string' ? <Fragment key={id}>{buildChild(id)}</Fragment> : null,
    )}
  </div>
));

const MetricGridApi = {
  name: 'MetricGrid',
  schema: z.object({ metrics: dynamicValue, ...CAPABILITIES }),
};

// Every molecule is individually wrapped: one malformed band must cost its own
// band and not the section. A boundary around the whole surface would let a
// single bad payload blank the agent's entire answer.
const MetricGridComponent = createComponentImplementation(
  MetricGridApi,
  ({ props, context }) => (
    <ErrorBoundary>
      <MetricGrid
        molecule={{ metrics: props.metrics, inspect: props.inspect, signal: props.signal }}
        onInspect={inspectHandler(context)}
      />
    </ErrorBoundary>
  ),
);

const CalloutApi = {
  name: 'Callout',
  schema: z.object({
    tone: dynamicString,
    lead: dynamicString,
    body: dynamicString,
    label: dynamicString,
    source: dynamicString,
    ...CAPABILITIES,
  }),
};

const CalloutComponent = createComponentImplementation(CalloutApi, ({ props, context }) => (
  <ErrorBoundary>
    <Callout
      molecule={{
        tone: props.tone,
        lead: props.lead,
        body: props.body,
        label: props.label,
        source: props.source,
        inspect: props.inspect,
        signal: props.signal,
      }}
      onInspect={inspectHandler(context)}
    />
  </ErrorBoundary>
));

const ScoreTableApi = {
  name: 'ScoreTable',
  schema: z.object({ rows: dynamicValue, total: dynamicValue, ...CAPABILITIES }),
};

const ScoreTableComponent = createComponentImplementation(ScoreTableApi, ({ props, context }) => (
  <ErrorBoundary>
    <ScoreTable
      molecule={{
        rows: props.rows,
        total: props.total,
        inspect: props.inspect,
        signal: props.signal,
      }}
      onInspect={inspectHandler(context)}
    />
  </ErrorBoundary>
));

const PhasePlanApi = {
  name: 'PhasePlan',
  schema: z.object({ phases: dynamicValue, ...CAPABILITIES }),
};

const PhasePlanComponent = createComponentImplementation(PhasePlanApi, ({ props, context }) => (
  <ErrorBoundary>
    <PhasePlan
      molecule={{ phases: props.phases, inspect: props.inspect, signal: props.signal }}
      onInspect={inspectHandler(context)}
    />
  </ErrorBoundary>
));

const ArcBeatsApi = {
  name: 'ArcBeats',
  schema: z.object({ beats: dynamicValue, ...CAPABILITIES }),
};

const ArcBeatsComponent = createComponentImplementation(ArcBeatsApi, ({ props, context }) => (
  <ErrorBoundary>
    <ArcBeats
      molecule={{ beats: props.beats, inspect: props.inspect, signal: props.signal }}
      onInspect={inspectHandler(context)}
    />
  </ErrorBoundary>
));

/**
 * The catalog the agent generates against.
 *
 * Components are listed explicitly rather than spread from anything, so this
 * file is an honest inventory of what can appear on screen. A2UI's logic
 * functions (`formatString`, the validation helpers) are carried over as-is —
 * they are expression helpers, not components, and cannot draw anything.
 */
export const signalCatalog = new Catalog(
  CATALOG_ID,
  [
    MoleculeStack,
    MetricGridComponent,
    CalloutComponent,
    ScoreTableComponent,
    PhasePlanComponent,
    ArcBeatsComponent,
  ],
  [...basicCatalog.functions.values()],
);
