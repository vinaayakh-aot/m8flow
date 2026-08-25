import { expect, test } from '@playwright/test';

import { editorCredentials, signInAsSharedRealmUser } from './helpers/auth';
import { morphElementType, openPropertiesPanelGroup } from './helpers/diagram';
import {
  SEED_MODEL_NAME,
  SEED_MODEL_ROUTE_ID,
  SEED_MODELER_PATH,
  SEED_USER_TASK_ELEMENT_ID,
  SECOND_SEED_MODEL_NAME,
  SECOND_SEED_MODEL_ROUTE_ID,
  SECOND_SEED_MODELER_PATH,
} from './helpers/fixtures';

/**
 * Phase 3 — Call Activity wiring (phased Task Configuration Parity plan,
 * §Phase 3). Implemented: BpmnCanvas.tsx now answers
 * `spiff.callactivity.search` (a new CallActivitySearchDialog picker over
 * every process model in the tenant — no reference implementation existed
 * to port; m8flow-frontend's own `onSearchProcessModels` is a no-op in its
 * one real consumer) and `spiff.callactivity.edit` (navigates to the called
 * process model's own modeler page, resolving its primary file the same way
 * ProcessModelOverview.tsx's own "Open in modeler" link does).
 *
 * Two scope corrections from the original plan, both found live:
 *
 * 1. The "drill-down overlay on the canvas shape" item doesn't apply here.
 *    Traced to m8flow-frontend's useDiagramImport.ts — that overlay only
 *    ever renders when `diagramType === 'readonly'` and real `tasks`
 *    (running-instance state) exist; it's a process-*instance*-viewer
 *    feature (jump into a call activity's live sub-instance), not a
 *    process-*model*-editor feature. BpmnCanvas.tsx is the editor, not an
 *    instance viewer — the "Launch Editor" button above is the
 *    editor-context equivalent, already covered.
 *
 * 2. No fixture *file* for a bpmn:CallActivity: m8flow-backend's own
 *    save-time validation (m8flow_backend.catalog.UNSUPPORTED_CONSTRUCTS)
 *    rejects `callActivity` outright ("Unsupported BPMN construct:
 *    callActivity", 400) — confirmed by actually trying to PUT one via
 *    seedProcessModelFile. Call Activity isn't executable by m8flow's
 *    engine today; this phase's own frontend wiring is still real and
 *    correct (Search/Launch Editor work purely client-side, no save
 *    involved), but there's no way to *persist* one. Works around this via
 *    morphElementType — bpmn-js's own "Change element" context-pad replace,
 *    entirely in-memory — on the seed model's real UserTask, rather than
 *    seeding a new file. Never calls Save, so the shared seed file is left
 *    untouched on disk.
 */
test.describe('m8flow-designer Process Modeler — Call Activity wiring (Phase 3)', () => {
  test.beforeEach(async ({ page }) => {
    await signInAsSharedRealmUser(page, editorCredentials());
    await page.goto(SEED_MODELER_PATH);
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    await morphElementType(page, SEED_USER_TASK_ELEMENT_ID, 'Call activity');
  });

  test('"Search" opens a picker that finds a real process model by name', async ({ page }) => {
    const group = await openPropertiesPanelGroup(page, 'called_element');
    await group.getByRole('button', { name: 'Search' }).click();

    const dialog = page.getByRole('dialog', { name: 'Search process models' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('textbox').fill(SEED_MODEL_NAME);
    await expect(dialog.getByText(SEED_MODEL_NAME, { exact: true })).toBeVisible();
  });

  test('selecting a search result sets Process ID and closes the picker', async ({ page }) => {
    const group = await openPropertiesPanelGroup(page, 'called_element');
    await group.getByRole('button', { name: 'Search' }).click();

    const dialog = page.getByRole('dialog', { name: 'Search process models' });
    await dialog.getByRole('textbox').fill(SEED_MODEL_NAME);
    await dialog.getByText(SEED_MODEL_NAME, { exact: true }).click();

    await expect(dialog).toHaveCount(0);
    await expect(group.getByLabel('Process ID')).toHaveValue(SEED_MODEL_ROUTE_ID);
  });

  test('"Launch Editor" navigates to the called process model\'s own modeler page', async ({
    page,
  }) => {
    // Targets a *different* model than the one currently open (the seed
    // model's own second real fixture) — proves real cross-model
    // navigation happened, not just that the already-open page stayed put.
    const group = await openPropertiesPanelGroup(page, 'called_element');
    await group.getByLabel('Process ID').fill(SECOND_SEED_MODEL_ROUTE_ID);
    await group.getByLabel('Process ID').blur();
    await group.getByRole('button', { name: 'Launch Editor' }).click();

    await expect(page).toHaveURL(new RegExp(SECOND_SEED_MODELER_PATH.replace(/:/g, '%3A|:')));
    await expect(page.locator('.djs-container')).toBeVisible();
  });
});
