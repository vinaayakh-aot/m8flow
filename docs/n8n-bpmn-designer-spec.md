# n8n-style BPMN designer — implementation spec

**Status:** approved for implementation. Decision made against the throwaway
prototype at `m8flow-frontend/prototype/n8n-bpmn/` (see
[Prototype reference](#prototype-reference)): **Variant A** ("inline
add-on-connection, accordion panel") is the direction. Variant C (command
palette) was found non-functional in review and is dropped — see
[Discarded: Variant C](#discarded-variant-c).

## Goal

Reskin the existing BPMN designer toward an n8n look and interaction model —
rounded task cards with colour/icon cues, dot-grid canvas, smooth bezier
connections, an inline "+" on a connection to insert a node into the flow —
with the canvas filling the whole viewport and the properties panel fixed to
the right quarter of the screen.

## Non-goals

- **No engine or file-format change.** BPMN 2.0 semantics, the
  `bpmn-js-spiffworkflow` moddle extension (`PreScript`/`PostScript`/
  `ServiceTaskOperator`/`InstructionsForEndUser`/etc.), and the XML
  `m8flow-bpmn-core` consumes are untouched. This is a visual/interaction
  skin over the existing three packages (`bpmn-js`, `bpmn-js-properties-panel`,
  `bpmn-js-spiffworkflow`), not a library swap and not a new modeling format.
- **No new dependencies.** Everything is built on packages already in
  `m8flow-frontend/package.json`.
- **Feature scope stays capped** at whatever `bpmn-js-spiffworkflow` already
  gives an authoring surface for. We are not adding UI for BPMN capabilities
  the engine doesn't execute.
- **Not a redesign of tenant/auth/RBAC.** This work is confined to the
  diagram-editor surface; it does not touch login, tenant selection, or
  permission checks.

## Prototype reference

`m8flow-frontend/prototype/n8n-bpmn/` (three variants, `?variant=A|B|C`,
standalone route bypassing the app shell/auth — see its `README.md`). Once
this spec lands, capture that tree to a throwaway branch per the `/prototype`
skill's convention; it should not stay on `main` once Variant A's logic has
been rewritten into production code below.

### Discarded: Variant C

The command-palette variant (`⌘K`/`Ctrl+K`, flat always-open panel) was
reviewed and found non-functional — the palette/FAB interaction didn't work
in practice. Because Variant A shares the same underlying modeler bootstrap
and shape-creation helpers (`shared/useN8nModeler.ts`,
`shared/canvasActions.ts`) and *does* work, the bug is isolated to Variant
C's own affordance code (keyboard capture, FAB, click-position tracking), not
the shared engine wiring — so this finding doesn't carry any risk into the
Variant A implementation below. No further investigation of Variant C is
planned; it's out of scope going forward.

## Architecture: where this lands

Everything below extends the real integration point, not the prototype:
`m8flow-frontend/src/components/ReactDiagramEditor.tsx` +
`useDiagramModeler.ts` + `useDiagramImport.ts`, following the same
`additionalModules` / event-listener-table patterns already used there for
`bpmn-js-spiffworkflow`.

### 1. Custom renderer module

Promote `prototype/n8n-bpmn/shared/n8nRenderer.ts` to a real module (e.g.
`src/components/bpmn/n8nRenderer.ts`), registered in `useDiagramModeler.ts`'s
`additionalModules` array alongside `spiffworkflow` and `m8flowExternalForm`.

The prototype only reskins `bpmn:Task` (+ subtypes), `bpmn:Gateway` (+
subtypes), and `bpmn:Event` (+ subtypes), delegating everything else to the
stock `bpmnRenderer`. Before this ships, audit every element type that
appears in real process models and either reskin it deliberately or confirm
the stock-renderer fallback reads acceptably next to the new shapes:

- Pools & lanes (`bpmn:Participant`, `bpmn:Lane`)
- Data objects & data stores (`bpmn-js-spiffworkflow`'s own `DataObjectRenderer`
  already overrides these — decide whether the n8n renderer wraps/extends
  that renderer or the two coexist as-is)
- Call activities, (sub)processes, boundary events, all event *definitions*
  (timer, message, signal, error, escalation — currently distinguished by
  bpmn-js's icon glyphs, which the simplified n8n shapes currently drop)
- Message flows, associations, group/text-annotation elements

### 2. Insert-on-connection interaction

Promote the hover-`+`-on-a-wire logic (`VariantA.tsx`'s `element.hover`
listener + `shared/canvasActions.ts`'s `insertShapeOnConnection`) into
`useDiagramModeler.ts`'s existing data-driven `listeners` table (the same
table `spiff.script.edit`, `elements.changed`, etc. already live in) rather
than as a parallel `useEffect`.

**Correctness gap to close before shipping:** the prototype's
`insertShapeOnConnection` calls `modeling.removeConnection` +
`createShape` + `createConnection` × 2 as four separate `Modeling` calls,
which land as four separate entries on bpmn-js's command stack — one Ctrl+Z
undoes only the last reconnection, leaving the diagram in a broken
intermediate state. Production version must wrap the whole insert as a
single compound command (a custom `CommandInterceptor`/command handler with
`preExecute`/`postExecute`, or `commandStack.execute` with a registered
compound command) so one undo reverts the entire insert atomically.

The node-type search list (`shared/sampleProcess.ts`'s `PALETTE_ENTRIES`) was
a fixed prototype stand-in; production must source it from whatever already
drives the stock bpmn-js palette today (so custom/extension element types
stay in sync automatically instead of needing manual updates in two places).

### 3. Properties panel restyle

The panel behavior itself is unchanged (stock `bpmn-js-properties-panel`
collapsible groups) — this is a CSS-only change. Promote
`prototype/n8n-bpmn/shared/n8n-theme.css`'s panel rules into the real
stylesheet already imported by `ReactDiagramEditor.tsx`. Verify against every
existing custom group (SpiffWorkflow's script/service-task/message/loop
panels, and m8flow's own "M8flow Connectors" group with its keep-open
MutationObserver logic in `useDiagramModeler.ts`) — the restyle must not
interfere with that existing open/close state preservation.

### 4. Toolbar

No new toolbar needed — `DiagramEditorControls.tsx` already provides
zoom-in/zoom-out/fit. Reposition it as a small floating pill
(top-left, over the canvas) instead of its current fixed placement, matching
the prototype's `.n8n-toolbar` styling. Do not reimplement zoom logic.

### 5. Full-viewport layout

`ReactDiagramEditor` is mounted inside the app shell (nav/header chrome
lives in the `spiffworkflow-frontend` sibling tree, not in this checkout —
confirm the exact host page, likely a `ProcessModelEditDiagram`-equivalent,
before implementing). Rather than trying to make the component's own
container naturally fill `100vw`/`100vh` (which would require every
ancestor in an app-shell page to cooperate, and risks fighting the nav/
header layout), implement the "fills the entire screen" requirement as a
**fixed full-viewport overlay** (`position: fixed; inset: 0; z-index` above
the app shell) toggled on when the diagram editor is the active view —
this works regardless of where the component is mounted in the page tree.
Confirm no existing fixed-position UI (snackbars, modals, the tenant-select
gate) ends up underneath it unexpectedly.

## Implementation order

1. Land the properties-panel CSS restyle (§3) — lowest risk, no interaction
   logic, immediately reviewable.
2. Land the renderer module (§1) for the element types already audited;
   fall back to stock rendering for anything not yet covered, called out
   explicitly in the PR description.
3. Land the full-viewport layout change (§5) once the host page is
   confirmed.
4. Land the insert-on-connection interaction (§2) with atomic undo — this is
   the highest-risk piece; ship it last, behind its own PR.
5. Reposition the toolbar (§4) — small, can ride along with either 3 or 4.

## Final polish checklist

Gaps the prototype knowingly skipped, to close before this is considered
done rather than "structurally right but rough":

- [ ] **Full element-type coverage** for the renderer (§1's audit) — event
      *definitions* (timer/message/signal/error/escalation icons), boundary
      events, sub-processes/call activities, pools/lanes, message flows,
      groups/annotations.
- [ ] **Atomic undo/redo** for insert-on-connection (§2's correctness gap).
- [ ] **Connection routing edge cases**: self-loops, multiple sequence flows
      between the same two elements, very short segments where the bezier
      smoothing produces a visible kink, default-flow marker (the small
      diagonal tick bpmn-js draws on a gateway's default outgoing flow).
- [ ] **Selection & hover states**: the custom shapes need their own
      selection outline / hover highlight styling — the prototype relies on
      bpmn-js's default selection box, which wasn't designed against
      pill-shaped nodes.
- [ ] **Resize/drag handles** on the reskinned shapes — not verified against
      the custom renderer; confirm they still align to the new shape
      geometry (especially the gateway diamond).
- [ ] **Accessibility**: keyboard-operable insert-on-connection (the
      prototype's picker is mouse/hover-only), focus management when the
      picker opens/closes, ARIA labelling for the new floating controls.
- [ ] **Node-type source of truth** (§2) — replace the prototype's hardcoded
      `PALETTE_ENTRIES` with whatever already drives the stock palette.
- [ ] **i18n**: every new user-facing string (picker placeholder, empty
      state, toolbar tooltips) needs to go through the existing `react-i18next`
      setup — the prototype hardcodes English.
- [ ] **Empty/error states**: what the "+" picker shows with zero matches
      (prototype has a bare "No matches" row), and what happens if
      `insertShapeOnConnection` fails partway (should not be possible once
      atomic per §2, but the failure path still needs a decision).
- [ ] **Performance on large diagrams**: hover-driven overlay creation/removal
      on every `element.hover` event hasn't been checked against a
      realistically large process model.
- [ ] **Test coverage**: unit tests for the renderer's type-dispatch, the
      insert-on-connection command, and a component test for the panel
      restyle not breaking the existing keep-group-open behavior.
- [ ] **Visual QA pass** against the real m8flow theme (MUI palette, dark
      mode if the app has one) — the prototype's colours were chosen freehand,
      not pulled from the app's design tokens.

## Testing/verification (per repo conventions)

- `npm run lint`, `npm test`, `npm run build` in `m8flow-frontend` for every
  PR in the implementation order above.
- No backend changes anticipated; if the node-type source-of-truth work (§2)
  or panel audit (§3) surfaces a need to touch `m8flow-backend`, treat that
  as a separate, explicitly-scoped change.
- This feature does not touch login/tenant/RBAC code, so the non-admin
  shared-realm regression check in `AGENTS.md` does not apply here.

## Open questions / risks

- **Host page unknown**: the real mount point's surrounding chrome lives in
  the `spiffworkflow-frontend` sibling repo, not present in this checkout —
  §5 must be validated against it directly before merging the layout change.
- **File overlap with other in-flight efforts**: `useDiagramModeler.ts` and
  the properties-panel CSS are also touched by the LGPL de-contamination
  map's frontend batches and its WEAK→HOLDS follow-on. Sequence this work
  to avoid colliding — check both maps for open tickets against these files
  before starting §2/§3.
- **`DataObjectRenderer` coexistence** (§1): whether the n8n renderer wraps
  `bpmn-js-spiffworkflow`'s existing data-object renderer or the two are
  kept as independent `BaseRenderer` registrations needs a decision during
  the audit, not assumed here.
