import type { Locator, Page } from '@playwright/test';

/**
 * Drags a real bpmn-js shape by (dx, dy) via actual mouse events — the
 * only way to flip diagram-js's command-stack-index dirty tracking without
 * touching internals (see BpmnCanvas.tsx). A small three-step approach then
 * settle steps mirrors real pointer movement closely enough for bpmn-js's
 * drag threshold to register a `shape.move` command.
 */
export async function dragShape(page: Page, shape: Locator, dx: number, dy: number): Promise<void> {
  const box = await shape.boundingBox();
  if (!box) {
    throw new Error('dragShape: target shape has no bounding box (not rendered?)');
  }
  const startX = box.x + box.width / 2;
  const startY = box.y + box.height / 2;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(startX + dx * 0.2, startY + dy * 0.2, { steps: 3 });
  await page.mouse.move(startX + dx, startY + dy, { steps: 8 });
  await page.mouse.up();
}

/**
 * Selects a bpmn-js element by id (a plain click, not a drag) so the
 * properties panel renders that element's groups. Every phase's e2e spec
 * needs this as its first step — factored out here rather than duplicated
 * per spec file.
 */
export async function selectElement(page: Page, elementId: string): Promise<Locator> {
  const shape = page.locator(`[data-element-id="${elementId}"]`);
  await shape.click();
  return shape;
}

/**
 * Locates a `@bpmn-io/properties-panel` group by its `data-group-id`
 * (bio-properties-panel prefixes every provider-supplied group id with
 * `group-`, confirmed against m8flow-frontend's useDiagramModeler.ts, which
 * targets the same `bpmn-js-properties-panel` DOM to keep the "M8flow
 * Connectors" group open across panel rebuilds).
 */
export function propertiesPanelGroup(page: Page, groupId: string): Locator {
  return page.locator(`.bio-properties-panel-group[data-group-id="group-${groupId}"]`);
}

async function isPropertiesPanelGroupOpen(group: Locator): Promise<boolean> {
  const classes = (await group.getAttribute('class')) ?? '';
  if (classes.includes('open')) return true;
  const header = group.locator(':scope > .bio-properties-panel-group-header');
  const headerClasses = (await header.getAttribute('class').catch(() => null)) ?? '';
  return headerClasses.includes('open');
}

/**
 * Opens a properties-panel group by id if it isn't already expanded.
 * Idempotent regardless of the group's default expand state, so callers
 * don't need to know which groups start open.
 */
export async function openPropertiesPanelGroup(page: Page, groupId: string): Promise<Locator> {
  const group = propertiesPanelGroup(page, groupId);
  await group.waitFor({ state: 'visible' });
  if (!(await isPropertiesPanelGroupOpen(group))) {
    await group.locator(':scope > .bio-properties-panel-group-header').click();
  }
  return group;
}

/**
 * Morphs an already-selected element into a different BPMN type via the
 * context pad's stock "Change element" (bpmn-js's own ReplaceMenuProvider —
 * not something m8flow-designer built), by clicking the target type's label
 * in the resulting popup. Only in-memory (diagram-js command stack) — no
 * Save involved.
 *
 * Exists because several BPMN construct types (bpmn:CallActivity,
 * bpmn:SendTask/ReceiveTask with a messageRef, correlation, non-event
 * bpmn:SubProcess, multi-instance loop characteristics) are rejected by
 * m8flow-backend's own save-time validation
 * (m8flow_backend.catalog._reject_unsupported_constructs's
 * UNSUPPORTED_CONSTRUCTS) — so seedProcessModelFile's PUT-based fixture
 * approach (used by Phases 1/2) can't create them at all. Replacing a real,
 * already-saved element's type live in the browser sidesteps that: the
 * properties panel and its `spiff.*` events work purely client-side, and
 * this never attempts to persist the result.
 */
export async function morphElementType(page: Page, elementId: string, targetTypeLabel: string): Promise<void> {
  await selectElement(page, elementId);
  await page.locator('.djs-context-pad .entry[data-action="replace"]').click();
  await page.getByText(targetTypeLabel, { exact: true }).click();
  // The properties panel's own re-render (new element type -> new provider
  // groups) lags slightly behind the popup-menu click resolving.
  await page.waitForTimeout(500);
}
