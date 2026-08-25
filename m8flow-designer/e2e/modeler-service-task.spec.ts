import { expect, test } from '@playwright/test';

import { editorCredentials, signInAsSharedRealmUser } from './helpers/auth';
import { openPropertiesPanelGroup, selectElement } from './helpers/diagram';
import { seedModelerPath } from './helpers/fixtures';
import { seedProcessModelFile } from './helpers/seedFixture';

/**
 * Phase 4 — Service Task connector wiring (phased Task Configuration Parity
 * plan, §Phase 4). Implemented: BpmnCanvas.tsx now answers
 * `spiff.service_tasks.requested` by fetching `GET /connectors-grouped` (the
 * real, working data source — m8flow-frontend's own `/service-tasks` call
 * has no matching backend route at all, confirmed by reading api.yml) and
 * flattening it from "grouped by connector" into the flat
 * `{id, parameters}[]` shape ServiceTaskOperatorSelect expects.
 *
 * Environment gap found live, not assumed: this dev stack's
 * `GET /connectors-grouped` returns `[]` today — `ServiceTaskRegistry`
 * starts with zero commands registered (m8flow_backend.secrets.list_connectors),
 * so there are no real connectors installed in this environment at all. The
 * "selecting an operator renders its own parameter fields" case from the
 * original plan is `test.fixme()`'d for exactly this reason — it isn't
 * blocked on designer code, it's blocked on there being anything to select.
 * The other two cases are written to hold regardless of how many (if any)
 * connectors are configured, by comparing against the *live* endpoint's own
 * response rather than assuming a fixed count — same principle as CHK-04's
 * earlier `>= 6` fix.
 */
const PHASE4_FILE = 'phase4-service-task.bpmn';
const SERVICE_TASK_ID = 'Activity_send_email';

const PHASE4_DIAGRAM_XML = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                   xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                   xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                   id="Definitions_phase4" targetNamespace="http://m8flow.org/e2e/phase4">
  <bpmn:process id="Process_phase4" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" />
    <bpmn:serviceTask id="${SERVICE_TASK_ID}" name="Send Email" />
    <bpmn:endEvent id="EndEvent_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="${SERVICE_TASK_ID}" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="${SERVICE_TASK_ID}" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_phase4">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="150" y="150" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Activity_send_email_di" bpmnElement="${SERVICE_TASK_ID}">
        <dc:Bounds x="250" y="128" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
        <dc:Bounds x="420" y="150" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
        <di:waypoint xmlns:di="http://www.omg.org/spec/DD/20100524/DI" x="186" y="168" />
        <di:waypoint xmlns:di="http://www.omg.org/spec/DD/20100524/DI" x="250" y="168" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2">
        <di:waypoint xmlns:di="http://www.omg.org/spec/DD/20100524/DI" x="350" y="168" />
        <di:waypoint xmlns:di="http://www.omg.org/spec/DD/20100524/DI" x="420" y="168" />
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;

/** How many total operations the live backend currently offers, across every connector. */
async function fetchRealOperationCount(page: import('@playwright/test').Page): Promise<number> {
  const response = await page.request.get('/v1.0/m8flow/connectors-grouped');
  const groups: Array<{ operations: unknown[] }> = await response.json();
  return groups.reduce((sum, g) => sum + g.operations.length, 0);
}

test.describe('m8flow-designer Process Modeler — Service Task connector wiring (Phase 4)', () => {
  test.beforeEach(async ({ page }) => {
    await signInAsSharedRealmUser(page, editorCredentials());
    await seedProcessModelFile(page, PHASE4_FILE, PHASE4_DIAGRAM_XML);
    await page.goto(seedModelerPath(PHASE4_FILE));
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    await selectElement(page, SERVICE_TASK_ID);
  });

  test('the connector operator dropdown completes a real round trip and matches the live catalog', async ({
    page,
  }) => {
    const expectedCount = await fetchRealOperationCount(page);

    const group = await openPropertiesPanelGroup(page, 'service_task_properties');
    const select = group.getByLabel('Operator ID');
    const optionCount = await select.locator('option').count();

    expect(optionCount).toBe(expectedCount);
  });

  test.fixme(
    'selecting an operator renders its own parameter fields',
    async ({ page }) => {
      // Blocked on environment data, not designer code: this dev stack's
      // ServiceTaskRegistry has zero commands registered, so
      // GET /connectors-grouped returns [] and there is nothing to select.
      // Un-skip once at least one connector is configured.
      const group = await openPropertiesPanelGroup(page, 'service_task_properties');
      await group.getByLabel('Operator ID').selectOption({ index: 1 });
      await expect(group.locator('input, select, textarea')).not.toHaveCount(0);
    },
  );

  test('the service task group stays open across the async connector-list round trip', async ({
    page,
  }) => {
    // `open` lives on the group's *header* element, not the group root
    // itself (confirmed live — @bpmn-io/properties-panel's own DOM, same
    // convention openPropertiesPanelGroup's internal check already uses).
    const group = await openPropertiesPanelGroup(page, 'service_task_properties');
    await page.waitForTimeout(500);
    await expect(group.locator(':scope > .bio-properties-panel-group-header')).toHaveClass(/open/);
  });
});
