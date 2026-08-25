import { expect, test } from '@playwright/test';

import { editorCredentials, signInAsSharedRealmUser } from './helpers/auth';
import { selectElement } from './helpers/diagram';
import { seedModelerPath } from './helpers/fixtures';
import { seedProcessModelFile } from './helpers/seedFixture';

/**
 * Phase 5 — Messages wiring (phased Task Configuration Parity plan,
 * §Phase 5). All `test.fixme()`: BpmnCanvas.tsx doesn't answer
 * `spiff.messages.requested`, `spiff.message.edit`/`.update`,
 * `spiff.add_message.requested`, or `spiff.message_schemas.requested` /
 * `spiff.msg_json_schema_editor.requested` yet.
 *
 * Uses a bpmn:SendTask (`isMessageElement()` in bpmn-js-spiffworkflow's
 * MessageHelpers.js accepts SendTask/ReceiveTask directly — no message
 * event definition required to render the Message group), so the fixture
 * stays a plain two-flow diagram like the other phases'.
 *
 * The group id this phase's provider renders under wasn't confirmed against
 * the shipped library the way earlier phases' group ids were (see the plan's
 * Phase 5 note) — locate it via `bpmn-js-spiffworkflow/app/spiffworkflow/
 * messages/propertiesPanel/elementLevelProvider/TaskEventMessageProvider.js`'s
 * `createMessageGroup` before un-skipping these, then swap the
 * `getMessageGroup()` placeholder below for the real
 * `propertiesPanelGroup(page, '<confirmed-id>')` call.
 */
const PHASE5_FILE = 'phase5-messages.bpmn';
const SEND_TASK_ID = 'Activity_notify';

const PHASE5_DIAGRAM_XML = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                   xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                   xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                   id="Definitions_phase5" targetNamespace="http://m8flow.org/e2e/phase5">
  <bpmn:process id="Process_phase5" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" />
    <bpmn:sendTask id="${SEND_TASK_ID}" name="Notify" />
    <bpmn:endEvent id="EndEvent_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="${SEND_TASK_ID}" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="${SEND_TASK_ID}" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_phase5">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="150" y="150" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Activity_notify_di" bpmnElement="${SEND_TASK_ID}">
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

test.describe('m8flow-designer Process Modeler — Messages wiring (Phase 5)', () => {
  test.beforeEach(async ({ page }) => {
    await signInAsSharedRealmUser(page, editorCredentials());
    await seedProcessModelFile(page, PHASE5_FILE, PHASE5_DIAGRAM_XML);
    await page.goto(seedModelerPath(PHASE5_FILE));
    await expect(page.getByText('Saved', { exact: true })).toBeVisible();
    await selectElement(page, SEND_TASK_ID);
  });

  test.fixme('the Message dropdown lists messages defined elsewhere in this process model', async () => {
    // spiff.messages.requested must be answered with every bpmn:message
    // declared across this model's own files (parsed from XML — no backend
    // route needed unless messages must be shared cross-model).
  });

  test.fixme('"+ Add Message" creates a new message and selects it', async () => {
    // spiff.add_message.requested / .returned round trip.
  });

  test.fixme('the message JSON schema selector lists *-schema.json files', async () => {
    // spiff.message_schemas.requested — same file-list-filtering pattern as
    // Phase 1's JSON Schema Filename field and Phase 2's DMN file field.
  });

  test.fixme('"Launch Editor" for the message schema opens the schema editor', async () => {
    // spiff.msg_json_schema_editor.requested.
  });
});
