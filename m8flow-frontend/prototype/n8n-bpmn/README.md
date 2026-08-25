# PROTOTYPE — n8n-style BPMN designer (throwaway)

**Question:** what should an n8n-styled BPMN workflow designer built on
`bpmn-js` + `bpmn-js-properties-panel` + `bpmn-js-spiffworkflow` look and
behave like, with the canvas filling the screen and the properties panel
fixed to the right quarter?

Three variants, switchable via `?variant=`, on a standalone route
(`/prototype-n8n-bpmn.html`) — **not** wired into the real app shell, router,
auth, or backend. Run it with the project's existing dev server:

```
npm start
```

then open `http://localhost:6841/prototype-n8n-bpmn.html` (or whatever
`PORT`/`HOST` you have configured). Use `?variant=A|B|C`, the on-screen
switcher, or the `←`/`→` arrow keys to flip between them.

All three keep the macro layout fixed (that part was already decided) and
the same n8n-ish visual skin (custom `BaseRenderer` module — rounded task
cards, diamond gateways, bezier connections, dot-grid canvas — see
`shared/n8nRenderer.ts`). BPMN 2.0 semantics and the spiffworkflow moddle
extension (`PreScript`/`PostScript`/`ServiceTaskOperator`/
`InstructionsForEndUser`) are untouched — this is a visual/interaction skin,
not an engine or file-format change. The sample process
(`shared/sampleProcess.ts`) exercises a few of those extensions so you can
click a node and see the real spiffworkflow properties-panel fields, not
just stock BPMN ones.

What's actually being varied — the open design question — is:

- **A — Inline add-on-connection, accordion panel.** Hover a wire, click the
  `+` at its midpoint, search-and-insert splices a node into the flow. No
  persistent palette/rail. Panel: stock collapsible groups, restyled.
- **B — Searchable rail + tabbed panel.** A collapsible left rail lists every
  node type, searchable, drag-and-drop onto the canvas. Panel: General /
  Behaviour / Advanced tabs filter the same underlying groups.
- **C — Command palette + flat panel.** No palette/rail at all; a bottom `+`
  FAB or `⌘K`/`Ctrl+K` opens a keyboard-navigable command palette that drops
  the node at your last canvas click. Panel: every group forced open, flat
  single column, no collapsing.

## Capture, once a variant wins

1. Note which variant (and which pieces of the others, if any) in the
   implementation ticket/commit.
2. Commit this whole `prototype/n8n-bpmn/` tree + `prototype-n8n-bpmn.html`
   to a throwaway branch — it's the primary source for "why did we land on
   this," not something to keep on `main`.
3. Rewrite the winning interaction/panel logic properly (real error handling,
   integrate with `useDiagramModeler.ts`'s existing event wiring, tests) when
   folding it into `ReactDiagramEditor.tsx` — this code was written under
   prototype constraints and should not go to production as-is.
