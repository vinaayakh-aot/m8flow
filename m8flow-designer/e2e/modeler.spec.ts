import { expect, test } from '@playwright/test';

import { editorCredentials, signInAsSharedRealmUser } from './helpers/auth';
import { dragShape } from './helpers/diagram';
import {
  SEED_MODEL_DETAIL_PATH,
  SEED_MODEL_NAME,
  SEED_MODELER_PATH,
  SEED_PRIMARY_FILE,
} from './helpers/fixtures';

/** A real task in the seed diagram, stable across runs (not a synthesized id). */
const DRAG_TARGET_ELEMENT_ID = 'Activity_submit_wfh';

async function gotoModeler(page: import('@playwright/test').Page) {
  await page.goto(SEED_MODELER_PATH);
  // Readiness gate, not a hard wait: dirty-tracking only attaches once
  // BpmnCanvas's importXML() resolves and the pill flips to Saved.
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();
  await expect(page.locator('.djs-container')).toBeVisible();
}

/**
 * CHK-06..09 — Process Modeler journeys through the live designer → backend
 * seam, against the real seeded wfh-approval.bpmn diagram. See
 * .e2e-agent/research.md for the fixture and .e2e-agent/cases.md for the
 * CHK-08 round-trip rationale (Save is a real, persisting PUT).
 */
test.describe('m8flow-designer Process Modeler', () => {
  test('CHK-06: Open in modeler opens the primary file in a real, editable canvas', async ({
    page,
  }) => {
    await signInAsSharedRealmUser(page, editorCredentials());
    await page.goto(SEED_MODEL_DETAIL_PATH);
    await expect(page.getByRole('heading', { name: SEED_MODEL_NAME, exact: true })).toBeVisible();

    await page.getByRole('link', { name: 'Open in modeler' }).click();

    await expect(page).toHaveURL(new RegExp(`modeler/${SEED_PRIMARY_FILE}`));
    await expect(page.locator('header')).toContainText(SEED_PRIMARY_FILE);
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    await expect(page.locator('.djs-container')).toBeVisible();
    // A real diagram, not an empty canvas — the seeded task is rendered.
    await expect(page.locator(`[data-element-id="${DRAG_TARGET_ELEMENT_ID}"]`)).toBeVisible();
  });

  test('CHK-07: modeler reports not-found for an unknown file name on a real model', async ({
    page,
  }) => {
    await signInAsSharedRealmUser(page, editorCredentials());

    await page.goto(SEED_MODELER_PATH.replace(SEED_PRIMARY_FILE, 'does-not-exist.bpmn'));

    await expect(page.getByText('File not found.', { exact: true })).toBeVisible();
    await expect(page.locator('.djs-container')).toHaveCount(0);
  });

  test('CHK-08: editing goes dirty, Save persists, and reload reflects the change', async ({
    page,
  }) => {
    await signInAsSharedRealmUser(page, editorCredentials());
    await gotoModeler(page);

    const target = page.locator(`[data-element-id="${DRAG_TARGET_ELEMENT_ID}"]`);
    const originalBox = await target.boundingBox();
    expect(originalBox).not.toBeNull();

    // 1. Edit -> dirty: Save button replaces the Saved pill.
    await dragShape(page, target, 60, 40);
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeVisible();
    await expect(page.getByText('Saved', { exact: true })).toHaveCount(0);

    // 2. Save -> pill returns to Saved.
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();

    // 3. Reload proves the PUT actually persisted (not just client state).
    await page.reload();
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    const movedBox = await target.boundingBox();
    expect(movedBox!.x).not.toBeCloseTo(originalBox!.x, 0);
    expect(movedBox!.y).not.toBeCloseTo(originalBox!.y, 0);

    // 4. Restore: drag back to the exact original position and save again,
    // so the (git-ignored but shared local) fixture is left as found.
    await dragShape(page, target, originalBox!.x - movedBox!.x, originalBox!.y - movedBox!.y);
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();

    await page.reload();
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    const restoredBox = await target.boundingBox();
    expect(restoredBox!.x).toBeCloseTo(originalBox!.x, 0);
    expect(restoredBox!.y).toBeCloseTo(originalBox!.y, 0);
  });

  test('CHK-09: Download produces the current diagram XML', async ({ page }) => {
    await signInAsSharedRealmUser(page, editorCredentials());
    await gotoModeler(page);

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Download' }).click(),
    ]);

    expect(download.suggestedFilename()).toBe(SEED_PRIMARY_FILE);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) {
      chunks.push(chunk as Buffer);
    }
    const content = Buffer.concat(chunks).toString('utf-8');
    expect(content).toContain('<?xml');
    expect(content).toContain('bpmn:definitions');
    expect(content).toContain(DRAG_TARGET_ELEMENT_ID);
  });
});
