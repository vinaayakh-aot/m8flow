/**
 * Restyles diagram node rendering to match `Process Modeler.dc.html`
 * (node-shape-styling ticket, Process Modeler visual fidelity map):
 * gunmetal-equivalent start events, success-colored end events, and
 * info-colored task-type icons on a light-gray-bordered box (rather than
 * bpmn-js's own black-on-black defaults).
 *
 * Composition, not reimplementation: this wraps bpmn-js's own
 * `bpmnRenderer` singleton (injected, not subclassed/`super`-called) —
 * calling its real `drawShape` to draw the element exactly as stock
 * bpmn-js would (box, embedded label, multi-instance/loop/compensation
 * markers, the lot), then recolors specific already-drawn children.
 * Reimplementing `renderTask`/`renderEvent` from scratch was considered
 * and rejected: those functions also own marker rendering (loop,
 * multi-instance, compensation, ad-hoc) that this seed diagram doesn't
 * happen to exercise but real diagrams do — reproducing them by hand
 * would risk silently dropping that rendering for the sake of a color
 * change. Registered as a higher-priority `bpmnRenderer`-adjacent
 * renderer via `additionalModules`, the same "override/augment the
 * DI-registered internals" pattern `customPalette.ts` and
 * `positionContextPadAboveTarget` (BpmnCanvas.tsx) already use.
 *
 * Scope: start events, end events, user/service/script/manual/business-
 * rule/send/receive tasks, generic tasks, call activities (the original
 * "biggest miss" ticket plus the task-subtype-styling follow-on),
 * all five gateway types (exclusive — the "decision node" the user
 * flagged as still untouched when the map was — wrongly — closed as
 * complete — plus parallel/inclusive/event-based/complex), sequence flow
 * arrows, pool/lane borders, Sub-Process/Ad-Hoc Sub-Process/Transaction
 * containers, every event-definition icon (message/timer/signal/error/
 * escalation/compensate/conditional/link/terminate) across Start/End/
 * Intermediate/Boundary events, and data/artifacts (Data Object/Store
 * References, Text Annotations, Groups, Associations, Message Flows) —
 * the full BPMN element-type inventory a real diagram renders is now
 * covered; see the map's own Decisions-so-far for how each category was
 * treated.
 *
 * Operation-group color palette (color-theory pass, live user feedback:
 * "we are using just 4 colours... the combination of blue and green on
 * some of the icons is genuinely ugly"). Reviewed against
 * https://www.w3.org/WAI/fundamentals/accessibility-intro/ (don't rely on
 * color alone to convey meaning — every group below is also a distinct
 * hand-drawn glyph shape, color is reinforcement, not the sole signal) and
 * basic color-wheel theory (spread hues around the wheel rather than
 * clustering near-adjacent ones, since two saturated near-adjacent hues —
 * exactly what blue ring-icon-on-blue-icon or blue-next-to-green was doing
 * — read as muddy/clashing at small icon sizes). Icons/markers are now
 * sorted into operation groups, each carrying its own hue *and* used
 * nowhere else, so no two groups fight for attention in the same glyph:
 *
 * - Structural (unchanged `TASK_STROKE`, neutral gray `--color-border`):
 *   containers and data holders that aren't "operations" at all — generic
 *   Task, Sub-Process, Ad-Hoc Sub-Process, Transaction, Pool, Lane, Group,
 *   Data Object/Store References. Deliberately left uncolored — WCAG's own
 *   "don't rely on color alone" cuts both ways: reserving color for
 *   elements that actually need distinguishing keeps it meaningful.
 * - Flow control (`FLOW_CONTROL_COLOR`, violet, new `--color-flow-control`
 *   token): all five gateway markers, the Ad-Hoc "~" marker, and the
 *   Terminate/Compensate/Conditional/Link event icons — all "control how
 *   the flow branches, loops, or ends" in kind.
 * - Timing (`TIMER_COLOR`, amber, `--color-warning`): the Timer icon only
 *   — the one operation group with a single, near-universal color
 *   convention (clocks are amber), so it gets a dedicated group of one.
 * - System (`SYSTEM_COLOR`, blue, `--color-info` — the file's original,
 *   now-narrowed `TASK_ICON_COLOR`): every task/activity icon (User,
 *   Service, Script, Manual, Business-Rule, Send, Receive Task, the Call
 *   Activity "+" marker) plus the Message/Signal/Escalation event icons
 *   and the Message Flow connector. **A later live-feedback pass merged
 *   what was originally two groups here** — User/Manual Task first got
 *   their own separate pink "human work" color, but live review showed
 *   that reads as an unintentional inconsistency, not a meaningful
 *   distinction: every *other* task icon shares one color, so having
 *   exactly one (Manual Task) in a different color looked like a mistake,
 *   not a category. All task/activity icons are now uniformly blue.
 * - Error handling (`ERROR_COLOR`, red, `--color-destructive`): the Error
 *   event icon only — the one place reusing the app's "destructive"
 *   semantic is a genuine conceptual match, not just a reused hex.
 *
 * **Unified event styling** (live user feedback: "events dont have a
 * common style. Schedule is different to the rest of the events. Schedule
 * looks better"): every typed event, of any kind (Start/End/Intermediate/
 * Boundary) and any event-definition type, now draws through
 * `drawUnifiedEventIcon` — a single ring, filled `--color-card`, stroked
 * in its own operation-group color, exactly matching the look Timer
 * ("Schedule") already had. Previously only Timer collapsed to one
 * colored ring; every other typed event kept bpmn-js's own stock ring(s)
 * (single for Start/End, double for Intermediate/Boundary) recolored
 * *neutral*, with only the small icon glyph carrying color — two
 * genuinely different constructions for what should read as one family.
 * Since ring and icon now always share the same hue, there's no remaining
 * ring-vs-icon mismatch left to clash in the first place (a stronger fix
 * than the prior pass's "make the end-event ring neutral for typed
 * events" workaround, which this supersedes). Untyped ("none") events are
 * unaffected — Start/Boundary/Intermediate keep a plain neutral ring
 * (`START_EVENT_STROKE`/`BOUNDARY_EVENT_STROKE`, now the same muted gray
 * as a sequence flow — see below), and an untyped End event keeps its
 * green ring, matching the mockup's own plain-end-event illustration.
 * Distinguishability between start/end doesn't depend on ring color in
 * the first place — bpmn-js already gives end events a 4px stroke vs.
 * start's ~2px (confirmed reading `BpmnRenderer.js`).
 *
 * **"Solid black" lines fixed** (live user feedback): `START_EVENT_STROKE`
 * and `BOUNDARY_EVENT_STROKE` used `--color-foreground` (near-black,
 * #1F2937 — the mockup's own "gunmetal" spec for a start event), which
 * read as inconsistent stray black lines next to the muted-gray sequence
 * flows and light-gray task borders everywhere else. Both now reuse
 * `SEQUENCE_FLOW_STROKE` directly.
 *
 * **Subtle task shadow** (live user feedback: "add a subtle shadow to
 * tasks"): every task/activity/container box (`applyTaskShadow`) gets a
 * soft `drop-shadow` on its outer rect — a restrained elevation cue, not a
 * heavy border, in the same spirit as this app's existing shadcn/ui card
 * shadows elsewhere.
 *
 * Also introduces this file's first **dashed** connection: a sequence
 * flow whose source is a `BoundaryEvent` (an exception/interrupt path) now
 * draws with a dash pattern, a non-color-based signal distinguishing it
 * from the diagram's normal "happy path" flow — the live user request
 * that prompted this pass explicitly invited trying dashed lines, and
 * boundary-event-sourced flows are a real, meaningful place to use one
 * (every other dashed line already in this file — Association, Group,
 * Message Flow — is a stock bpmn-js default, not a customization).
 */
import { is } from 'bpmn-js/lib/util/ModelUtil';
import { append as svgAppend, attr as svgAttr, create as svgCreate } from 'tiny-svg';

const HIGH_PRIORITY = 2000;

// Reuses the app's own theme tokens (src/styles/index.css) rather than the
// mockup's raw --aot-gunmetal/--aot-sky-blue/--status-success names, same
// convention as every other restyle in this map.
const TASK_STROKE = 'var(--color-border)';
const SEQUENCE_FLOW_STROKE = 'var(--color-muted-foreground)';
// Every "neutral" ring in the diagram — Start's plain ring, Boundary's/
// Intermediate's double ring when untyped — reuses the exact same gray as
// a sequence flow arrow. Previously these used `--color-foreground`
// (near-black, the mockup's own "gunmetal" spec for a start event); live
// user feedback flagged that as reading like stray "solid black" lines
// inconsistent with everything else in the canvas, so this now matches
// the muted gray already established for connectors. End's own ring stays
// `--color-success` green (untyped only — see the unified-event-icon
// comment below for typed events) since that's a distinct, intentional
// "this is a terminal/success state" signal, not a stray neutral.
const START_EVENT_STROKE = SEQUENCE_FLOW_STROKE;
const END_EVENT_STROKE = 'var(--color-success)';
// A boundary-event-sourced sequence flow (an exception/interrupt path) —
// see this file's own top-of-file comment on why a dash pattern, not a
// color, is the differentiator here.
const EXCEPTION_FLOW_DASH = '4,4';

// Operation-group color palette — see the top-of-file comment for the full
// rationale (color-wheel spread, WCAG 1.4.11 contrast checks, "don't rely
// on color alone" via distinct glyph shapes per group).
const SYSTEM_COLOR = 'var(--color-info)'; // every task/activity icon + system/communication events
const FLOW_CONTROL_COLOR = 'var(--color-flow-control)'; // gateways + terminate/compensate/conditional/link
const TIMER_COLOR = 'var(--color-warning)'; // Timer icon only
const ERROR_COLOR = 'var(--color-destructive)'; // Error icon only
// Same treatment as a plain start event ring — a boundary event is a
// (usually interrupting) event attached to an activity, closer in kind to
// a start/intermediate event than to the task it's attached to. No
// mockup guidance exists either way (its own illustration has no
// boundary event at all); decided live rather than left unstyled.
const BOUNDARY_EVENT_STROKE = SEQUENCE_FLOW_STROKE;
// Subtle task elevation — live user feedback: "add a subtle shadow to
// tasks," refined twice since: first to reduce top/left bleed, then to a
// specific value the user supplied directly:
// `box-shadow: rgba(149, 157, 165, 0.2) 0px 8px 24px`. Translated to
// `filter: drop-shadow(...)` rather than the literal `box-shadow`
// property — SVG shape elements (the `<rect>`/`<polygon>` this targets)
// don't reliably support `box-shadow` across browsers the way HTML boxes
// do, whereas `drop-shadow` is the SVG-safe equivalent already proven
// live in this file. `drop-shadow(offsetX offsetY blurRadius color)`
// takes the same three length values and color in the same order
// `box-shadow` does (no spread-radius support, but none was specified
// here), so this is a direct value carry-over, not a re-tuned one — the
// larger blur-vs-offset ratio here (24px blur vs. 8px/0px offset) is a
// deliberately soft, diffuse "floating card" look, wider than the tighter
// directional shadow the prior tuning pass produced.
const TASK_SHADOW = 'drop-shadow(0px 8px 24px rgba(149, 157, 165, 0.2))';
// Cross-participant message flow (data-artifacts-styling ticket) reuses
// `SYSTEM_COLOR` — the "system & communication" operation-group color — on
// purpose, and the ticket's own Question flagged wanting a message flow to
// read as visually different from a same-participant sequence flow "at a
// glance": bpmn-js already dashes it distinctly (`10, 11` vs a sequence
// flow's solid line), and this adds a distinct *color* on top of that.
// Kept as its own named constant since the reasoning (communication
// connector, not a task icon) is genuinely distinct from `SYSTEM_COLOR`'s
// other uses, even though the value is identical.
const MESSAGE_FLOW_STROKE = SYSTEM_COLOR;
// bpmn-js's own unstyled default fill (`BpmnRenderUtil.js`'s `white`
// constant, `'white'`) — never overridden here (see recolorOuterStroke's
// comment), so this is what the cutout/background paths inside task-type
// icons actually carry and must be matched *against* to know which of an
// icon's own child shapes to leave alone.
const DEFAULT_SHAPE_FILL = 'white';

// Matches the canvas's own dot-grid background (diagram-chrome.css's
// `.djs-container` rule, ticket 01) — same 22px pitch, same 1.1px dot
// radius, same `--color-border` dot color — so a lane's background reads
// as "the canvas's own texture, made visible here" rather than an
// unrelated new pattern. Live user feedback, after three failed attempts
// at a translucent/flat-color swimlane background (see this ticket's own
// "Reverted" section): texture, not color/opacity, is what actually
// distinguishes a lane from a white task box in this app's near-white
// palette.
const DOT_PATTERN_ID = 'm8flow-lane-dot-pattern';
const DOT_PATTERN_PITCH = 22;
const DOT_PATTERN_RADIUS = 1.1;

/**
 * Lazily defines (once per diagram) and returns a `url(#...)` reference
 * to the dot pattern above, as an SVG `<pattern>` in the diagram's own
 * `<defs>` — the SVG-native equivalent of the canvas's CSS
 * `radial-gradient` background, since a `<rect fill="...">` inside the
 * diagram can only reference an SVG paint server, not a CSS background
 * image. Checked by id rather than tracked in a variable: bpmn-js tears
 * down and recreates this renderer's own gfx groups on reimport/undo, but
 * never the root `<svg>` itself, so the pattern only needs creating once
 * per diagram lifetime, not once per render call.
 */
function ensureLaneDotPattern(rootSvg: SVGElement | null): string {
  if (!rootSvg) return 'none';

  if (rootSvg.querySelector(`#${DOT_PATTERN_ID}`)) {
    return `url(#${DOT_PATTERN_ID})`;
  }

  let defs = rootSvg.querySelector('defs') as SVGElement | null;
  if (!defs) {
    defs = svgCreate('defs');
    svgAppend(rootSvg, defs);
  }

  const pattern = svgCreate('pattern', {
    id: DOT_PATTERN_ID,
    patternUnits: 'userSpaceOnUse',
    width: DOT_PATTERN_PITCH,
    height: DOT_PATTERN_PITCH,
  });
  const dot = svgCreate('circle', {
    cx: DOT_PATTERN_PITCH / 2,
    cy: DOT_PATTERN_PITCH / 2,
    r: DOT_PATTERN_RADIUS,
    fill: 'var(--color-border)',
  });
  svgAppend(pattern, dot);
  svgAppend(defs, pattern);

  return `url(#${DOT_PATTERN_ID})`;
}

/**
 * bpmn-js's `bpmn:UserTask`/`bpmn:ServiceTask` handlers call
 * `renderTask()` first (box + embedded label + any markers), then append
 * their own type-icon shapes directly afterward — confirmed by reading
 * `BpmnRenderer.js`'s source for both handlers. That makes the icon
 * shapes always the *last* N children appended to the shape's gfx group,
 * regardless of how many box/label/marker children preceded them — the
 * basis for the tail-slice recolor below, instead of a fragile absolute
 * index or an over-eager "recolor anything gray" sweep that would also
 * catch marker icons on other diagrams.
 */
const ICON_TAIL_COUNT: Record<string, number> = {
  'bpmn:UserTask': 3, // TASK_TYPE_USER_1/2/3 paths
  'bpmn:ServiceTask': 4, // 2 white cutout circles (left as-is) + 2 gear paths
  // Call Activity keeps bpmn-js's own "+" collapsed-call marker (a real,
  // meaningful indicator, not decorative) rather than a custom icon —
  // task-subtype-styling ticket, decided live: recolor it in place instead
  // of replacing it, same tail-slice technique as User/ServiceTask.
  'bpmn:CallActivity': 1,
  // Container-styling ticket, same "recolor a real structural indicator
  // in place, don't replace it" decision as Call Activity: AdHocSubProcess
  // draws exactly one "~" marker after its box+label (confirmed reading
  // `renderTaskMarkers`/`taskMarkerRenderers.AdhocMarker` — a single
  // `drawMarker` call) — a genuine icon glyph, colored per
  // `ICON_COLOR_BY_TYPE` below like every other task-type icon.
  // `bpmn:SubProcess` itself needs no entry — expanded, non-ad-hoc,
  // non-loop, non-compensation sub-processes draw *no* marker children at
  // all (confirmed reading `renderSubProcess`'s own `taskMarkers` call), so
  // its border-only recolor already falls out of the generic branch with
  // no extra work. (`bpmn:Transaction`'s own extra inner rect — its
  // classic "double border" look — is handled separately: it's a border
  // variant, not an icon, and coloring it like a task icon made the whole
  // box read as blue.)
  'bpmn:AdHocSubProcess': 1,
};

/**
 * Per-type icon color for everything `ICON_TAIL_COUNT` recolors in place —
 * operation-group palette (see top-of-file comment). User Task, Service
 * Task, and Call Activity are all "system" (blue) — live user feedback,
 * after an earlier pass gave User/Manual Task their own separate pink
 * "human work" color: seeing every *other* task icon share one color and
 * only Manual Task differ read as an unintentional inconsistency, not a
 * meaningful category, so task-type icons are now uniformly blue
 * regardless of subtype. The Ad-Hoc "~" marker stays "flow control"
 * (violet, alongside the gateways it shares an execution-order concern
 * with) — a genuinely different kind of marker, not a task-type icon.
 */
const ICON_COLOR_BY_TYPE: Record<string, string> = {
  'bpmn:UserTask': SYSTEM_COLOR,
  'bpmn:ServiceTask': SYSTEM_COLOR,
  'bpmn:CallActivity': SYSTEM_COLOR,
  'bpmn:AdHocSubProcess': FLOW_CONTROL_COLOR,
};

/**
 * bpmn-js's own icon-path count per task subtype, read from each
 * handler in `BpmnRenderer.js` (same discipline as every prior custom
 * icon in this file) — the basis for how many trailing children
 * `drawCustomTaskSubtypeIcon` below must strip before drawing its own
 * replacement glyph:
 * - ScriptTask, ManualTask, SendTask: 1 path each.
 * - BusinessRuleTask: 2 paths (header block + header divider).
 * - ReceiveTask: 1 path in the common (non-"instantiate") case — this
 *   map's seed diagram never sets `instantiate`, so the 2-child
 *   (start-circle + path) case isn't handled; flagged, not silently
 *   assumed universal.
 */
const CUSTOM_TASK_ICON_TAIL_COUNT: Record<string, number> = {
  'bpmn:ScriptTask': 1,
  'bpmn:ManualTask': 1,
  'bpmn:BusinessRuleTask': 2,
  'bpmn:SendTask': 1,
  'bpmn:ReceiveTask': 1,
};

/**
 * Per-type color for the custom task-subtype glyphs (operation-group
 * palette, see top-of-file comment) — Script/Manual/Business-Rule/Send/
 * Receive Task are all "system" (blue), same "every task icon shares one
 * color" fix as `ICON_COLOR_BY_TYPE` above (Manual Task previously stood
 * out in pink; live user feedback confirmed that read as inconsistent).
 */
const CUSTOM_TASK_ICON_COLOR: Record<string, string> = {
  'bpmn:ScriptTask': SYSTEM_COLOR,
  'bpmn:ManualTask': SYSTEM_COLOR,
  'bpmn:BusinessRuleTask': SYSTEM_COLOR,
  'bpmn:SendTask': SYSTEM_COLOR,
  'bpmn:ReceiveTask': SYSTEM_COLOR,
};

/**
 * Custom task-subtype icons (task-subtype-styling ticket, same "create
 * custom icons for the elements" instruction as the gateway's X and the
 * boundary event's clock) — hand-drawn stroke-only line art in the same
 * ~16x16 top-left icon area bpmn-js's own glyphs occupy, replacing them
 * outright rather than recoloring in place. Script reuses the folded-
 * document motif already established elsewhere in this codebase
 * (`BpmnCanvas.tsx`'s own `SCRIPT_ICON_SVG`, used for the pre/post-script
 * overlay badges) for visual consistency within the app, not just this
 * file.
 */
function drawCustomTaskSubtypeIcon(parentGfx: SVGElement, elementType: string) {
  const paths: Record<string, string> = {
    'bpmn:ScriptTask': 'M8,6 L18,6 L23,11 L23,24 L8,24 Z M18,6 L18,11 L23,11',
    'bpmn:ManualTask': 'M9,15 L19,15 L19,23 L9,23 Z M11,15 L11,10 M14,15 L14,9 M17,15 L17,10 M9,17 L6,19 L9,21',
    'bpmn:BusinessRuleTask': 'M7,8 L21,8 L21,22 L7,22 Z M7,13 L21,13 M7,18 L21,18 M14,8 L14,22',
    'bpmn:SendTask': 'M6,12 L22,5 L15,22 L12,14 Z M12,14 L22,5',
    'bpmn:ReceiveTask': 'M14,6 L14,17 M9,13 L14,18 L19,13 M6,21 L22,21',
  };
  const d = paths[elementType];
  if (!d) return;

  const path = svgCreate('path', {
    d,
    fill: 'none',
    stroke: CUSTOM_TASK_ICON_COLOR[elementType] ?? SYSTEM_COLOR,
    strokeWidth: 1.6,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  });
  svgAppend(parentGfx, path);
}

/**
 * Custom gateway-marker icon (gateway-styling ticket — the user's
 * "decision node" complaint, plus the standing "create custom icons for
 * the elements" instruction: this replaces bpmn-js's own stock
 * `PathMap`-derived "X" glyph outright, rather than recoloring it in
 * place the way `recolorTaskIcon` treats task-type icons). Hand-drawn to
 * match the clean stroke-only, round-cap line-art already established by
 * `customPalette.ts`/`diagram-chrome.css`'s own icon set (e.g. the
 * palette's own gateway button icon) — two crossing diagonals sized to
 * ~32% of the gateway's own bounding box, centered, rather than bpmn-js's
 * filled/mitered default.
 */
function drawCustomExclusiveGatewayMarker(parentGfx: SVGElement, element: any) {
  const cx = element.width / 2;
  const cy = element.height / 2;
  const r = Math.min(element.width, element.height) * 0.16;

  const path = svgCreate('path', {
    d: `M${cx - r},${cy - r} L${cx + r},${cy + r} M${cx + r},${cy - r} L${cx - r},${cy + r}`,
    fill: 'none',
    stroke: FLOW_CONTROL_COLOR,
    strokeWidth: 2.2,
    strokeLinecap: 'round',
  });
  svgAppend(parentGfx, path);
}

/**
 * Custom markers for the remaining gateway types (other-gateway-styling
 * ticket, same standing instruction as the exclusive gateway's X above):
 * Parallel gets a `+`, Inclusive an `O` ring, Event-Based a plain ring
 * (our seed diagram never sets `eventGatewayType`, so stock bpmn-js draws
 * only an unornamented inner ring for it too — confirmed reading
 * `BpmnRenderer.js`'s own handler — so a ring is the faithful custom
 * equivalent, not an arbitrary simplification), Complex a 3-line
 * asterisk. All in the same stroke-only, round-cap line-art as every
 * other custom icon in this file.
 */
function drawCustomGatewayMarker(parentGfx: SVGElement, element: any, kind: string) {
  const cx = element.width / 2;
  const cy = element.height / 2;
  const r = Math.min(element.width, element.height) * 0.16;

  const common = { fill: 'none', stroke: FLOW_CONTROL_COLOR, strokeWidth: 2.2, strokeLinecap: 'round' as const };

  if (kind === 'parallel') {
    svgAppend(parentGfx, svgCreate('path', { d: `M${cx - r},${cy} L${cx + r},${cy} M${cx},${cy - r} L${cx},${cy + r}`, ...common }));
  } else if (kind === 'inclusive' || kind === 'eventBased') {
    svgAppend(parentGfx, svgCreate('circle', { cx, cy, r, fill: 'none', stroke: FLOW_CONTROL_COLOR, strokeWidth: 2.2 }));
  } else if (kind === 'complex') {
    const d = [0, 60, 120].flatMap((deg) => {
      const rad = (deg * Math.PI) / 180;
      const dx = r * Math.cos(rad);
      const dy = r * Math.sin(rad);
      return [`M${cx - dx},${cy - dy}`, `L${cx + dx},${cy + dy}`];
    }).join(' ');
    svgAppend(parentGfx, svgCreate('path', { d, ...common }));
  }
}

/**
 * Custom timer-boundary-event icon (boundary-event-styling ticket, same
 * "create custom icons for the elements" instruction as the gateway's X).
 * Stock bpmn-js draws a genuinely fussy timer glyph for
 * `bpmn:TimerEventDefinition` — an inner circle, a clock-hands path, *and*
 * 12 individual tick-mark line segments (confirmed by reading
 * `BpmnRenderer.js`'s own `eventIconRenderers['bpmn:TimerEventDefinition']`)
 * — 14 elements just for the icon. Recoloring all 14 in place (the
 * `recolorTaskIcon` tail-slice approach) would have worked, but a
 * from-scratch minimal clock face (one ring, two hands, no tick marks)
 * reads more clearly at the small size boundary events render at, and
 * matches the same clean, sparse line-art already established for the
 * gateway's custom X.
 *
 * Sized to exactly match bpmn-js's own outer-ring radius formula
 * (`Math.round((width + height) / 4)`, read directly from `drawCircle` in
 * `BpmnRenderer.js`) — the same radius `getShapePath`/`getCirclePath`
 * use to crop connection waypoints to this shape's edge. A second HITL
 * follow-up found this the hard way: the first pass's smaller ~34%-sized
 * circle left a visible gap between the clock and its attached sequence
 * flow, because diagram-js still crops connections to the *model's*
 * width/height (unchanged by this renderer) regardless of how small the
 * drawn icon is — only matching that same radius makes the two coincide.
 * Filled `--color-card` (not `none`), also per live feedback — a
 * transparent face let the canvas's own dot-grid background show through
 * the icon, unlike every other opaque event ring already drawn.
 */
function drawCustomTimerIcon(parentGfx: SVGElement, element: any) {
  const cx = element.width / 2;
  const cy = element.height / 2;
  const r = Math.round((element.width + element.height) / 4);

  const face = svgCreate('circle', {
    cx,
    cy,
    r,
    fill: 'var(--color-card)',
    stroke: TIMER_COLOR,
    strokeWidth: 1.6,
  });
  svgAppend(parentGfx, face);

  const hands = svgCreate('path', {
    d: `M${cx},${cy} L${cx},${cy - r * 0.65} M${cx},${cy} L${cx + r * 0.55},${cy}`,
    fill: 'none',
    stroke: TIMER_COLOR,
    strokeWidth: 1.6,
    strokeLinecap: 'round',
  });
  svgAppend(parentGfx, hands);
}

/**
 * Typed-event-icon-styling ticket: extends the Timer-only treatment
 * above to the remaining 8 event-definition types (Timer itself already
 * has its own dedicated `drawCustomTimerIcon`, kept as-is). Every event
 * kind draws its ring(s) first, then calls the shared `renderEventIcon`
 * dispatcher for whichever definition the event actually has — so
 * "strip everything after the ring(s), draw a custom glyph instead" is
 * uniform across Start/End/Intermediate/Boundary events regardless of
 * definition type, unlike the gateway/task tickets, which needed a
 * distinct tail-count per *type*. `bpmn:MultipleEventDefinition`/
 * `ParallelMultipleEventDefinition` are permanently out of scope —
 * `bpmn-moddle`'s own schema doesn't define them at all (confirmed in
 * ticket 09).
 */
function getEventDefinitionType(element: any): string | undefined {
  const eventDefinitions = element.businessObject?.eventDefinitions ?? [];
  return eventDefinitions[0]?.$type;
}

/**
 * Per-event-definition-type color (operation-group palette, see
 * top-of-file comment): Message/Signal/Escalation are "system &
 * communication" (blue — broadcast/notify events read as the same kind of
 * "digital" concern as messaging); Error is its own dedicated "error
 * handling" red; Compensate/Conditional/Link/Terminate are all "flow
 * control" (violet), alongside the gateways — each one redirects,
 * unwinds, or ends the flow rather than doing work or communicating.
 */
const EVENT_DEFINITION_COLOR: Record<string, string> = {
  'bpmn:MessageEventDefinition': SYSTEM_COLOR,
  'bpmn:SignalEventDefinition': SYSTEM_COLOR,
  'bpmn:EscalationEventDefinition': SYSTEM_COLOR,
  'bpmn:ErrorEventDefinition': ERROR_COLOR,
  'bpmn:CompensateEventDefinition': FLOW_CONTROL_COLOR,
  'bpmn:ConditionalEventDefinition': FLOW_CONTROL_COLOR,
  'bpmn:LinkEventDefinition': FLOW_CONTROL_COLOR,
  'bpmn:TerminateEventDefinition': FLOW_CONTROL_COLOR,
  // Timing — see `drawCustomTimerIcon`, reused directly below rather than
  // duplicated: this map entry exists for documentation/lookup
  // completeness, not because the branch below reads it (the clock glyph
  // hardcodes `TIMER_COLOR` internally).
  'bpmn:TimerEventDefinition': TIMER_COLOR,
};

/**
 * Hand-drawn stroke-only glyphs for the 8 non-Timer event-definition
 * types (Timer is handled one level up, by `drawUnifiedEventIcon` below),
 * sized relative to the event's own ring radius `r` (the same
 * `Math.round((width + height) / 4)` formula `drawCustomTimerIcon`
 * established) so they scale consistently whatever the event's actual
 * pixel size. Returns without drawing anything for an unrecognized/
 * out-of-scope type (Multiple) — `drawUnifiedEventIcon` only calls this
 * when it's about to draw something, so an unhandled type intentionally
 * leaves nothing drawn rather than silently guessing.
 */
function drawCustomEventDefinitionIcon(parentGfx: SVGElement, element: any, defType: string | undefined) {
  const cx = element.width / 2;
  const cy = element.height / 2;
  const r = Math.round((element.width + element.height) / 4);
  const color = (defType && EVENT_DEFINITION_COLOR[defType]) ?? SYSTEM_COLOR;
  const common = { fill: 'none', stroke: color, strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

  if (defType === 'bpmn:MessageEventDefinition') {
    const hw = r * 0.55;
    const hh = r * 0.4;
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx - hw},${cy - hh} L${cx + hw},${cy - hh} L${cx + hw},${cy + hh} L${cx - hw},${cy + hh} Z M${cx - hw},${cy - hh} L${cx},${cy + hh * 0.2} L${cx + hw},${cy - hh}`,
      ...common,
    }));
  } else if (defType === 'bpmn:SignalEventDefinition') {
    const s = r * 0.6;
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx},${cy - s} L${cx + s * 0.87},${cy + s * 0.5} L${cx - s * 0.87},${cy + s * 0.5} Z`,
      ...common,
    }));
  } else if (defType === 'bpmn:ErrorEventDefinition') {
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx - r * 0.5},${cy - r * 0.65} L${cx + r * 0.2},${cy - r * 0.05} L${cx - r * 0.15},${cy + r * 0.1} L${cx + r * 0.5},${cy + r * 0.65}`,
      ...common,
    }));
  } else if (defType === 'bpmn:EscalationEventDefinition') {
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx - r * 0.5},${cy + r * 0.35} L${cx},${cy - r * 0.5} L${cx + r * 0.5},${cy + r * 0.35} M${cx},${cy - r * 0.5} L${cx},${cy + r * 0.55}`,
      ...common,
    }));
  } else if (defType === 'bpmn:CompensateEventDefinition') {
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx + r * 0.05},${cy - r * 0.55} L${cx - r * 0.5},${cy} L${cx + r * 0.05},${cy + r * 0.55} Z M${cx + r * 0.6},${cy - r * 0.55} L${cx + r * 0.05},${cy} L${cx + r * 0.6},${cy + r * 0.55} Z`,
      fill: color,
      stroke: color,
      strokeWidth: 1,
      strokeLinejoin: 'round',
    }));
  } else if (defType === 'bpmn:ConditionalEventDefinition') {
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx - r * 0.55},${cy - r * 0.4} L${cx + r * 0.55},${cy - r * 0.4} M${cx - r * 0.55},${cy} L${cx + r * 0.55},${cy} M${cx - r * 0.55},${cy + r * 0.4} L${cx + r * 0.55},${cy + r * 0.4}`,
      ...common,
    }));
  } else if (defType === 'bpmn:LinkEventDefinition') {
    svgAppend(parentGfx, svgCreate('path', {
      d: `M${cx - r * 0.55},${cy} L${cx + r * 0.3},${cy} M${cx},${cy - r * 0.4} L${cx + r * 0.55},${cy} L${cx},${cy + r * 0.4}`,
      ...common,
    }));
  } else if (defType === 'bpmn:TerminateEventDefinition') {
    svgAppend(parentGfx, svgCreate('circle', { cx, cy, r: r * 0.45, fill: color, stroke: 'none' }));
  }
}

/**
 * Unified event badge (operation-group color palette, follow-on pass) —
 * live user feedback: "events dont have a common style. Schedule is
 * different to the rest of the events. Schedule looks better." Timer's
 * own look (one ring, filled `--color-card`, stroked in its own color)
 * was both the structural odd-one-out *and* the one users preferred over
 * every other typed event's "stock ring recolored neutral + separately
 * colored icon floating inside" construction. This draws every typed
 * event through the same single-ring badge Timer already used, so ring
 * and icon always share one hue — Timer is still special-cased first
 * since its own glyph (`drawCustomTimerIcon`) draws its *own* ring, and
 * drawing a second generic one first would double up.
 *
 * Callers strip *every* existing child (both rings, for Intermediate/
 * Boundary) before calling this — same "replace outright" pattern as
 * every custom icon in this file.
 */
function drawUnifiedEventIcon(parentGfx: SVGElement, element: any, defType: string) {
  if (defType === 'bpmn:TimerEventDefinition') {
    drawCustomTimerIcon(parentGfx, element);
    return;
  }

  const cx = element.width / 2;
  const cy = element.height / 2;
  const r = Math.round((element.width + element.height) / 4);
  const color = EVENT_DEFINITION_COLOR[defType] ?? SYSTEM_COLOR;

  svgAppend(parentGfx, svgCreate('circle', {
    cx,
    cy,
    r,
    fill: 'var(--color-card)',
    stroke: color,
    strokeWidth: 1.6,
  }));

  drawCustomEventDefinitionIcon(parentGfx, element, defType);
}

function recolorTaskIcon(parentGfx: SVGElement, elementType: string) {
  const tailCount = ICON_TAIL_COUNT[elementType];
  if (!tailCount) return;
  const color = ICON_COLOR_BY_TYPE[elementType] ?? SYSTEM_COLOR;

  const children = Array.from(parentGfx.childNodes) as SVGElement[];
  children.slice(-tailCount).forEach((node) => {
    if (!(node instanceof SVGElement)) return;
    // Read via the CSSStyleDeclaration (`.style.stroke`/`.style.fill`),
    // not `getAttribute('stroke'|'fill')` — found live, the hard way (see
    // recolorContainerStrokes's own comment for the full story): bpmn-js's
    // `drawPath` bundles stroke/fill into one inline `style="..."`
    // attribute via its own `lineStyle()` helper, so a plain
    // `getAttribute` read always came back `null` and silently skipped
    // every icon path — this task-icon recolor has never actually
    // fired since ticket 03 first wrote it. `.style.stroke`/`.style.fill`
    // correctly parse the inline style string regardless.
    const stroke = node.style.stroke;
    if (stroke && stroke !== 'none') {
      svgAttr(node, 'stroke', color);
    }
    // Only recolor solid-filled icon strokes (bpmn-js draws the user-task
    // head as fill=strokeColor) — the two white cutout fills (task-type
    // icon backgrounds, ServiceTask's gear cutouts) already equal the
    // default fill color and must stay untouched, or the icon reads as a
    // solid blob.
    const fill = node.style.fill;
    if (fill && fill !== 'none' && fill !== DEFAULT_SHAPE_FILL) {
      svgAttr(node, 'fill', color);
    }
  });
}

/**
 * Recolors just the outer box/ring's own stroke — always the *first*
 * child bpmn-js appends (the box `rect` for tasks, the ring `circle` for
 * events), before any embedded label or type-icon children.
 *
 * Deliberately **not** done by passing a custom `attrs.stroke` into
 * `bpmnRenderer.drawShape()` — found live, the hard way: bpmn-js's own
 * `renderEmbeddedLabel()` reuses `attrs.stroke` as the *label's* text
 * color too (`getLabelColor(element, defaultLabelColor,
 * defaultStrokeColor, attrs.stroke)` in `BpmnRenderer.js`), so passing a
 * light gray box-border override also silently turned "Submit WFH
 * Request"'s own label text light gray — nearly illegible against the
 * white task fill. Recoloring only the specific already-drawn `rect`/
 * `circle` element after the fact sidesteps that coupling entirely: the
 * label text (and, for typed start/end events, any event-type icon) never
 * gets touched, so it keeps bpmn-js's own default dark color.
 */
function recolorOuterStroke(parentGfx: SVGElement, color: string) {
  const outer = parentGfx.firstElementChild as SVGElement | null;
  if (outer) {
    svgAttr(outer, 'stroke', color);
  }
}

/**
 * Applies `TASK_SHADOW` to the outer box (always the first child, same as
 * `recolorOuterStroke`) of every task/activity/container shape — live user
 * feedback: "add a subtle shadow to tasks." Set via the real DOM `.style`
 * property rather than `svgAttr`, since `filter` isn't a presentation
 * attribute bpmn-js's own `lineStyle()`/`shapeStyle()` helpers already
 * bundle into `style="..."` the way `stroke`/`fill` are (see
 * `recolorContainerStrokes`'s own comment for that story) — there's no
 * existing inline style to fight with here, so a direct `.style.filter`
 * write is the simplest correct approach.
 */
function applyTaskShadow(parentGfx: SVGElement) {
  const outer = parentGfx.firstElementChild as SVGElement | null;
  if (outer) {
    outer.style.filter = TASK_SHADOW;
  }
}

/**
 * Softens a gateway diamond's four sharp corners — live user feedback:
 * "add a subtle rounding to the edges of gates." bpmn-js draws a gateway
 * as a single `<polygon>` (`drawDiamond` in `BpmnRenderer.js`), not a
 * `<path>` with per-corner arcs, so there's no `rx`/`ry`-style radius to
 * set the way `drawRect`'s task boxes already get one from bpmn-js
 * itself. `stroke-linejoin: round` is the SVG-native equivalent for a
 * polygon: it rounds the *join* between each pair of edges using the
 * existing stroke width as the rounding radius, which reads as a subtle
 * softening at this diamond's small size without redrawing the shape's
 * geometry from scratch.
 */
function roundGatewayCorners(parentGfx: SVGElement) {
  const diamond = parentGfx.firstElementChild as SVGElement | null;
  if (diamond) {
    svgAttr(diamond, 'stroke-linejoin', 'round');
  }
}

/**
 * Pool/lane border recolor. Unlike every other shape here, this doesn't
 * assume a fixed child index: `bpmn:Participant`'s handler
 * (`BpmnRenderer.js`) draws its own rect, then — only when expanded — a
 * horizontal/vertical divider `<line>` separating the pool's name header
 * from its lanes, *before* the name label text; `bpmn:Lane` draws just
 * its rect, then its own rotated name label directly, no divider. Rather
 * than special-case each shape's own exact structure, this recolors every
 * *non-text* child's stroke (the rect, and the pool's divider line if
 * present) and explicitly skips any `<text>` element — the same safety
 * property `recolorOuterStroke`'s own comment documents (labels reuse
 * `attrs.stroke` as their own color when a caller passes it; skipping
 * `<text>` here matters only as a defensive belt-and-braces check, since
 * this renderer never passes a custom `attrs.stroke` into the wrapped
 * `drawShape()` call in the first place).
 *
 * Recolors unconditionally, with no `getAttribute('stroke')` pre-check —
 * found live, the hard way: `drawRect`'s own `shapeStyle()` helper
 * (`BpmnRenderer.js`) bundles `stroke`/`fill`/`strokeWidth`/etc. into a
 * single inline `style="..."` attribute rather than separate XML
 * attributes (confirmed by dumping the real DOM — this is true even for
 * the task boxes ticket 03 already recolored). `getAttribute('stroke')`
 * can't see a color living inside `style`, so a guard built on it always
 * read `null` and silently skipped every child; `svgAttr`'s own *write*
 * path already handles this correctly regardless (it's what let ticket
 * 03's task-box recolor work in the first place) — only the read-based
 * gate here was the bug.
 */
function recolorContainerStrokes(parentGfx: SVGElement, color: string) {
  Array.from(parentGfx.children).forEach((child) => {
    if (child.tagName.toLowerCase() === 'text') return;
    svgAttr(child as SVGElement, 'stroke', color);
  });
}

export default function CustomBpmnRenderer(this: any, eventBus: any, bpmnRenderer: any) {
  const self = this;

  eventBus.on(['render.shape'], HIGH_PRIORITY, (_evt: any, context: any) => {
    const { element, gfx } = context;
    if (!self.canRender(element)) return undefined;
    return self.drawShape(gfx, element);
  });

  eventBus.on(['render.connection'], HIGH_PRIORITY, (_evt: any, context: any) => {
    const { element, gfx } = context;
    if (!self.canRender(element)) return undefined;
    return self.drawConnection(gfx, element);
  });

  this._bpmnRenderer = bpmnRenderer;
}

CustomBpmnRenderer.$inject = ['eventBus', 'bpmnRenderer'];

CustomBpmnRenderer.prototype.canRender = function canRender(element: any) {
  // External labels (diagram-js's own synthetic `type: 'label'` shapes,
  // e.g. a start/end event's name floating below its ring) share their
  // *target* element's businessObject — `is(label, 'bpmn:EndEvent')` is
  // true for them too. Found live: without this guard, an end event's
  // label got recolored right along with its ring (this function's own
  // `recolorOuterStroke` reached into the label's one-child gfx group and
  // repainted its `<text>`), which the mockup doesn't do — its labels stay
  // a neutral gray regardless of the element's own color.
  if (element.type === 'label') {
    return false;
  }

  return (
    is(element, 'bpmn:StartEvent') ||
    is(element, 'bpmn:EndEvent') ||
    is(element, 'bpmn:UserTask') ||
    is(element, 'bpmn:ServiceTask') ||
    is(element, 'bpmn:ExclusiveGateway') ||
    is(element, 'bpmn:ParallelGateway') ||
    is(element, 'bpmn:InclusiveGateway') ||
    is(element, 'bpmn:EventBasedGateway') ||
    is(element, 'bpmn:ComplexGateway') ||
    is(element, 'bpmn:SequenceFlow') ||
    is(element, 'bpmn:BoundaryEvent') ||
    is(element, 'bpmn:IntermediateCatchEvent') ||
    is(element, 'bpmn:IntermediateThrowEvent') ||
    is(element, 'bpmn:Participant') ||
    is(element, 'bpmn:Lane') ||
    is(element, 'bpmn:Task') ||
    is(element, 'bpmn:ScriptTask') ||
    is(element, 'bpmn:ManualTask') ||
    is(element, 'bpmn:BusinessRuleTask') ||
    is(element, 'bpmn:SendTask') ||
    is(element, 'bpmn:ReceiveTask') ||
    is(element, 'bpmn:CallActivity') ||
    is(element, 'bpmn:SubProcess') ||
    is(element, 'bpmn:AdHocSubProcess') ||
    is(element, 'bpmn:Transaction') ||
    is(element, 'bpmn:DataObjectReference') ||
    is(element, 'bpmn:DataStoreReference') ||
    is(element, 'bpmn:TextAnnotation') ||
    is(element, 'bpmn:Group') ||
    is(element, 'bpmn:Association') ||
    is(element, 'bpmn:MessageFlow')
  );
};

CustomBpmnRenderer.prototype.drawShape = function drawShape(
  this: any,
  parentGfx: SVGElement,
  element: any,
) {
  // No custom attrs passed in at all — draw exactly as stock bpmn-js
  // would (default black/white), then recolor specific already-drawn
  // children. See recolorOuterStroke's own comment for why this, not an
  // `attrs` override, is the approach.
  const shape = this._bpmnRenderer.drawShape(parentGfx, element);

  if (is(element, 'bpmn:StartEvent')) {
    // Unified-event-styling pass: a typed start event now gets the same
    // single-ring colored badge as every other typed event (see
    // `drawUnifiedEventIcon`'s own comment) — strip the whole shape and
    // redraw. An untyped ("none") event keeps its plain neutral ring.
    const defType = getEventDefinitionType(element);
    if (defType && defType !== 'bpmn:MultipleEventDefinition') {
      Array.from(parentGfx.children).forEach((child) => parentGfx.removeChild(child));
      drawUnifiedEventIcon(parentGfx, element, defType);
    } else {
      recolorOuterStroke(parentGfx, START_EVENT_STROKE);
    }
  } else if (is(element, 'bpmn:EndEvent')) {
    // Same unified treatment as Start above. An untyped ("none") end event
    // keeps its green ring — nothing to clash with, matching the mockup's
    // own plain-end-event illustration.
    const defType = getEventDefinitionType(element);
    if (defType && defType !== 'bpmn:MultipleEventDefinition') {
      Array.from(parentGfx.children).forEach((child) => parentGfx.removeChild(child));
      drawUnifiedEventIcon(parentGfx, element, defType);
    } else {
      recolorOuterStroke(parentGfx, END_EVENT_STROKE);
    }
  } else if (is(element, 'bpmn:IntermediateCatchEvent') || is(element, 'bpmn:IntermediateThrowEvent')) {
    // Intermediate events draw a *double* ring like boundary events do
    // when untyped (confirmed reading `bpmn:IntermediateEvent`'s shared
    // handler) — collapsed to the same single unified badge as every other
    // typed event when a definition is present.
    const defType = getEventDefinitionType(element);
    if (defType && defType !== 'bpmn:MultipleEventDefinition') {
      Array.from(parentGfx.children).forEach((child) => parentGfx.removeChild(child));
      drawUnifiedEventIcon(parentGfx, element, defType);
    } else {
      recolorOuterStroke(parentGfx, BOUNDARY_EVENT_STROKE);
      const innerRing = parentGfx.children[1] as SVGElement | undefined;
      if (innerRing) {
        svgAttr(innerRing, 'stroke', BOUNDARY_EVENT_STROKE);
      }
    }
  } else if (is(element, 'bpmn:ExclusiveGateway')) {
    recolorOuterStroke(parentGfx, TASK_STROKE);
    roundGatewayCorners(parentGfx);
    // Stock bpmn-js only draws the "X" marker at all when the diagram's
    // own `isMarkerVisible` DI flag is set (`BpmnRenderer.js`'s
    // `bpmn:ExclusiveGateway` handler) — respect that: a second child
    // means the stock marker was drawn, so swap it for the custom one;
    // no second child means the source diagram deliberately has a bare
    // diamond, and this leaves it bare rather than forcing an X in.
    const marker = parentGfx.children[1];
    if (marker) {
      parentGfx.removeChild(marker);
      drawCustomExclusiveGatewayMarker(parentGfx, element);
    }
  } else if (
    is(element, 'bpmn:ParallelGateway') ||
    is(element, 'bpmn:InclusiveGateway') ||
    is(element, 'bpmn:EventBasedGateway') ||
    is(element, 'bpmn:ComplexGateway')
  ) {
    recolorOuterStroke(parentGfx, TASK_STROKE);
    roundGatewayCorners(parentGfx);
    // Each of these draws exactly one marker child after the diamond in
    // our seed diagram's own configuration (confirmed reading each
    // handler in `BpmnRenderer.js` — Event-Based only draws its extra
    // event-glyph paths when `eventGatewayType` is set, which our
    // diagram never does, so it's the same "diamond + one ring" shape as
    // the others here). Same swap pattern as the exclusive gateway above.
    const kind = is(element, 'bpmn:ParallelGateway')
      ? 'parallel'
      : is(element, 'bpmn:InclusiveGateway')
        ? 'inclusive'
        : is(element, 'bpmn:EventBasedGateway')
          ? 'eventBased'
          : 'complex';
    const marker = parentGfx.children[1];
    if (marker) {
      parentGfx.removeChild(marker);
      drawCustomGatewayMarker(parentGfx, element, kind);
    }
  } else if (is(element, 'bpmn:BoundaryEvent')) {
    // Same unified treatment as every other event kind above — this also
    // covers Timer's own former dedicated branch (drop the stock double
    // ring entirely, per live feedback: "remove the outer circles
    // surrounding the clock for scheduled tasks"), since
    // `drawUnifiedEventIcon` special-cases Timer the same way. A boundary
    // event without any definition (a malformed/edge-case diagram) falls
    // back to the plain double-ring neutral treatment.
    const defType = getEventDefinitionType(element);
    if (defType && defType !== 'bpmn:MultipleEventDefinition') {
      Array.from(parentGfx.children).forEach((child) => parentGfx.removeChild(child));
      drawUnifiedEventIcon(parentGfx, element, defType);
    } else {
      recolorOuterStroke(parentGfx, BOUNDARY_EVENT_STROKE);
      const innerRing = parentGfx.children[1] as SVGElement | undefined;
      if (innerRing) {
        svgAttr(innerRing, 'stroke', BOUNDARY_EVENT_STROKE);
      }
    }
  } else if (is(element, 'bpmn:Participant') || is(element, 'bpmn:Lane')) {
    recolorContainerStrokes(parentGfx, TASK_STROKE);
    if (is(element, 'bpmn:Lane')) {
      // Live user feedback, this ticket's 4th attempt at a visible
      // swimlane background (see "Reverted" above for the first three):
      // "add a dot pattern background" — texture instead of a translucent
      // or flat color, which this app's near-white palette kept
      // defeating. Lane rect is always the first child (see
      // recolorContainerStrokes's own comment on `Lane`'s structure).
      const laneRect = parentGfx.firstElementChild as SVGElement | null;
      if (laneRect) {
        svgAttr(laneRect, 'fill', ensureLaneDotPattern(parentGfx.ownerSVGElement));
        svgAttr(laneRect, 'fill-opacity', 1);
      }
    }
  } else if (is(element, 'bpmn:Transaction')) {
    // Found live: recoloring the inner double-border rect via the generic
    // `recolorTaskIcon`/`TASK_ICON_COLOR` path (the same technique
    // AdHocSubProcess's marker uses) made the whole box read as blue —
    // the inner rect is a *border* variant (the classic transaction
    // "double border" look), not an icon, so it gets the same
    // `TASK_STROKE` as the outer border, not the info-blue icon color.
    recolorOuterStroke(parentGfx, TASK_STROKE);
    applyTaskShadow(parentGfx);
    const innerBorder = parentGfx.lastElementChild as SVGElement | null;
    if (innerBorder && innerBorder !== parentGfx.firstElementChild) {
      svgAttr(innerBorder, 'stroke', TASK_STROKE);
    }
  } else if (
    is(element, 'bpmn:DataObjectReference') ||
    is(element, 'bpmn:DataStoreReference') ||
    is(element, 'bpmn:Group')
  ) {
    // Data-artifacts-styling ticket. All three draw exactly one visible
    // child (the folded-document path, the data-store cylinder path, or the
    // dashed rect, respectively — confirmed reading each handler in
    // `BpmnRenderer.js`) with no embedded label of their own (`bpmn:Group`
    // in particular renders *no* name label at all in this bpmn-js version,
    // despite the moddle schema modeling `categoryValueRef`), so the plain
    // `recolorOuterStroke` (first child) used everywhere else in this file
    // applies directly. Grouped with the container family (`TASK_STROKE`,
    // the same light gray as pool/lane/task borders) rather than the
    // connector family below — these are standalone box-like elements, not
    // lines.
    recolorOuterStroke(parentGfx, TASK_STROKE);
  } else if (is(element, 'bpmn:TextAnnotation')) {
    // Text Annotation draws an invisible sizing rect *first*
    // (`fill: 'none', stroke: 'none'`), then the visible bracket path,
    // then its own text label — confirmed reading `BpmnRenderer.js`'s own
    // handler. Unlike the three shapes above, its `renderLabel` call *does*
    // couple to a passed-in `attrs.stroke` via `getLabelColor`'s own
    // `overrideColor` — the same label-coupling hazard `recolorOuterStroke`'s
    // own comment already documents for tasks/embedded labels — so this
    // targets the bracket path specifically (`children[1]`, not
    // `firstElementChild`) rather than reusing `recolorOuterStroke`, leaving
    // the annotation's own text at bpmn-js's default color untouched.
    // Connector/annotation family (`SEQUENCE_FLOW_STROKE`, the same muted
    // gray as a sequence flow and — see `drawConnection` below —
    // Association), not the box family above: this is closer in kind to an
    // annotative device than a structural container.
    const bracket = parentGfx.children[1] as SVGElement | undefined;
    if (bracket) {
      svgAttr(bracket, 'stroke', SEQUENCE_FLOW_STROKE);
    }
  } else if (CUSTOM_TASK_ICON_TAIL_COUNT[element.type]) {
    // Script/Manual/BusinessRule/Send/Receive Task — task-subtype-styling
    // ticket. Strip bpmn-js's own stock icon path(s) and draw a genuinely
    // custom glyph, same "replace outright" pattern as the gateway's X
    // and the boundary event's clock (not a recolor-in-place, unlike
    // User/ServiceTask below — decided per the standing "create custom
    // icons" instruction).
    recolorOuterStroke(parentGfx, TASK_STROKE);
    applyTaskShadow(parentGfx);
    const tailCount = CUSTOM_TASK_ICON_TAIL_COUNT[element.type];
    Array.from(parentGfx.children)
      .slice(-tailCount)
      .forEach((child) => parentGfx.removeChild(child));
    drawCustomTaskSubtypeIcon(parentGfx, element.type);
  } else {
    // Generic bpmn:Task (border only, no icon), Call Activity (border +
    // recolor its existing "+" marker in place), User/ServiceTask (border
    // + recolor their icons in place), Sub-Process/Ad-Hoc Sub-Process
    // (fall through here too — no dedicated branch of their own).
    recolorOuterStroke(parentGfx, TASK_STROKE);
    applyTaskShadow(parentGfx);
    recolorTaskIcon(parentGfx, element.type);
  }

  return shape;
};

/**
 * Sequence flows — the user's "arrows did not change" complaint. Unlike
 * shapes, this *does* pass a custom `attrs.stroke` straight into the
 * wrapped `bpmnRenderer.drawConnection()` call, not a post-hoc DOM
 * recolor: read live, `bpmn:SequenceFlow`'s handler
 * (`BpmnRenderer.js`) has no embedded-label call to fight over
 * `attrs.stroke` the way tasks/events did (a sequence flow's own name,
 * e.g. "Approved"/"Rejected" off the gateway, is always an *external*
 * label — a separate `type: 'label'` element this renderer already
 * excludes via `canRender`'s own guard). `attrs.stroke` also flows into
 * every marker the handler creates for this connection (the arrowhead,
 * plus any conditional-flow/default-flow marker) via bpmn-js's own
 * `marker()` helper, which mints a brand-new `<marker>` def per call
 * (confirmed live: no caching/dedup by color at all) — so passing our
 * color once here recolors the line *and* every arrowhead variant this
 * connection could have, with no separate one-time `<defs>` patch needed.
 */
CustomBpmnRenderer.prototype.drawConnection = function drawConnection(
  this: any,
  parentGfx: SVGElement,
  element: any,
) {
  if (is(element, 'bpmn:SequenceFlow')) {
    // A sequence flow whose source is a BoundaryEvent is an exception/
    // interrupt path, not the diagram's normal "happy path" — dashed per
    // this file's top-of-file comment, a non-color-based signal per WCAG's
    // own "don't rely on color alone" guidance. Found live: unlike
    // `stroke`, `attrs.strokeDasharray` does *not* survive into
    // `drawConnectionSegments` — `bpmn:SequenceFlow`'s own handler calls
    // `pickAttrs(attrs, ['fill', 'stroke'])` first, silently dropping any
    // other attrs key — so this sets it as a post-hoc DOM attribute on the
    // returned path instead, the same "recolor after the fact" discipline
    // every shape branch in this file already uses.
    const isExceptionFlow = is(element.source, 'bpmn:BoundaryEvent');
    const connection = this._bpmnRenderer.drawConnection(parentGfx, element, { stroke: SEQUENCE_FLOW_STROKE });
    if (isExceptionFlow) {
      svgAttr(connection, 'stroke-dasharray', EXCEPTION_FLOW_DASH);
    }
    return connection;
  }
  if (is(element, 'bpmn:Association')) {
    // Data-artifacts-styling ticket. `renderAssociation` never calls
    // `renderLabel` at all — confirmed reading `BpmnRenderer.js` — so, like
    // sequence flow above, a custom `attrs.stroke` can be passed straight
    // through with no label-coupling risk. Same muted gray as a sequence
    // flow (the connector/annotation family, see the TextAnnotation shape
    // branch above); bpmn-js's own dashed pattern (`0, 5`) already
    // distinguishes it from a solid sequence flow.
    return this._bpmnRenderer.drawConnection(parentGfx, element, { stroke: SEQUENCE_FLOW_STROKE });
  }
  if (is(element, 'bpmn:MessageFlow')) {
    // `renderMessageFlow`'s own message-name label *does* couple to
    // `attrs.stroke` via the same `getLabelColor` override — but only when
    // `semantic.get('messageRef')` is set, which this map's seed diagram's
    // two message flows never do (confirmed reading the source XML) — safe
    // here. Flagged, not silently assumed universal: a message flow with a
    // named `messageRef` would have that label recolored too, untested
    // since no such flow exists in this diagram.
    return this._bpmnRenderer.drawConnection(parentGfx, element, { stroke: MESSAGE_FLOW_STROKE });
  }
  return this._bpmnRenderer.drawConnection(parentGfx, element);
};

export const customRendererModule = {
  __init__: ['customBpmnRenderer'],
  customBpmnRenderer: ['type', CustomBpmnRenderer],
};
