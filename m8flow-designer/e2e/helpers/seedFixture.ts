import type { Page } from '@playwright/test';

import { BACKEND_BASE_URL, SEED_MODEL_ROUTE_ID } from './fixtures';

/**
 * Seeds a phase-dedicated BPMN/DMN file into the seed process model, via the
 * same `PUT /process-models/{id}/files/{file_name}` route BpmnCanvas's own
 * Save button calls (processes_controller.put_process_model_file — writes a
 * new file into an *existing* model directory, it isn't restricted to file
 * names that already exist there).
 *
 * Deliberately never targets SEED_PRIMARY_FILE: each phase's coverage
 * diagram gets its own file name (see e2e/fixtures/*.bpmn), so seeding one
 * phase's fixture can never corrupt another phase's, or CHK-06..09's,
 * expectations of wfh-approval.bpmn's own *content*. Re-running a phase's
 * spec just overwrites its own fixture back to the known-good XML, so no
 * cleanup is needed for that file's own tests.
 *
 * It DOES grow the model's real file *count* permanently, though — there's
 * no delete-file route for process models (only templates have one), so
 * every phase's seeded files accumulate in the shared model directory
 * forever. Confirmed the hard way: processes.spec.ts's CHK-04 originally
 * hardcoded "Files (6)" and broke the first time this phase's spec ran
 * against a live stack. Any assertion elsewhere in this repo's e2e suite
 * that counts this model's files needs to tolerate that growth (>=, not
 * ===) rather than assume a fixed number.
 *
 * Uses `page.request` (not a fresh APIRequestContext) so it fires from the
 * page's own already-authenticated session — call this after
 * `signInAsSharedRealmUser`, not before.
 */
export async function seedProcessModelFile(
  page: Page,
  fileName: string,
  xmlContent: string,
  modelRouteId: string = SEED_MODEL_ROUTE_ID,
): Promise<void> {
  const accessToken = await readAccessTokenCookie(page);
  const encodedId = modelRouteId.split(':').map(encodeURIComponent).join(':');
  const url = `${BACKEND_BASE_URL}/v1.0/m8flow/process-models/${encodedId}/files/${encodeURIComponent(fileName)}`;

  const response = await page.request.put(url, {
    data: xmlContent,
    headers: {
      'Content-Type': 'application/octet-stream',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  if (!response.ok()) {
    throw new Error(
      `seedProcessModelFile: PUT ${fileName} failed with ${response.status()} — ${await response.text()}`,
    );
  }
}

/** Same cookie api.ts's apiGet/saveProcessModelFileContent read to build the Bearer header. */
async function readAccessTokenCookie(page: Page): Promise<string | null> {
  const cookies = await page.context().cookies();
  return cookies.find((cookie) => cookie.name === 'access_token')?.value ?? null;
}
