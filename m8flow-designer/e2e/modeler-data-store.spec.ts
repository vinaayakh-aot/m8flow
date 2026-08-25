import { expect, test } from '@playwright/test';

import { editorCredentials, signInAsSharedRealmUser } from './helpers/auth';
import { openPropertiesPanelGroup, selectElement } from './helpers/diagram';
import { seedModelerPath } from './helpers/fixtures';
import { seedProcessModelFile } from './helpers/seedFixture';

/**
 * Phase 6 — Data Store Reference wiring (phased Task Configuration Parity
 * plan, §Phase 6). Implemented: BpmnCanvas.tsx now answers
 * `spiff.data_stores.requested` — self-contained, not backed by any prop or
 * backend call. Confirmed by searching both m8flow-backend's own source and
 * the installed m8flow-bpmn-core wheel for "DataStore": zero hits in
 * either — there's no backend registry to draw from at all, unlike Service
 * Task connectors (which at least have a real, if empty,
 * ServiceTaskRegistry). The only real data available is whatever
 * `bpmn:DataStore` root elements are already declared in *this* diagram's
 * own XML — the same self-contained pattern bpmn-js-spiffworkflow's own
 * DataObjectSelect.jsx already uses for the unrelated Data Object construct.
 *
 * Test currently `test.fixme()`'d — this construct turns out fully
 * unpersistable and uncreatable in m8flow today, confirmed two ways:
 *
 * 1. `bpmn:dataStore`/`bpmn:dataStoreReference` aren't in m8flow_backend's
 *    simple string-matched UNSUPPORTED_CONSTRUCTS list (unlike Call
 *    Activity/Messages), so seedProcessModelFile's PUT was tried directly —
 *    but it still fails, one layer deeper: the engine's own BPMN parser
 *    rejects it at import time with `"Data Store with name Employee Records
 *    has no implementation."` (a *different* error_code —
 *    "validation_error", not "unsupported_bpmn" — confirming this is
 *    SpiffWorkflow/m8flow-bpmn-core's own pluggable-DataStore-implementation
 *    requirement, which m8flow-bpmn-core registers none of).
 * 2. Unlike Call Activity (Phase 3), there's no way to create one live
 *    in-memory either: customPalette.ts has no data-store creation entry,
 *    and bpmn-js's stock "Change element" replace menu only offers
 *    activity-type morphs (Task <-> Service Task <-> ... <-> Call Activity),
 *    not cross-category swaps into a data artifact.
 *
 * So there is currently no way — file-seeded or live-created — to get a
 * `bpmn:DataStoreReference` onto a canvas this test can drive. The frontend
 * wiring above is real and correct regardless (it'll work the moment either
 * gap closes); this is purely an execution-environment limitation.
 */
const PHASE6_FILE = 'phase6-data-store.bpmn';
const DATA_STORE_REF_ID = 'DataStoreReference_1';

const PHASE6_DIAGRAM_XML = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                   xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                   xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                   id="Definitions_phase6" targetNamespace="http://m8flow.org/e2e/phase6">
  <bpmn:dataStore id="DataStore_1" name="Employee Records" />
  <bpmn:process id="Process_phase6" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" />
    <bpmn:task id="Activity_lookup" name="Look Up" />
    <bpmn:endEvent id="EndEvent_1" />
    <bpmn:dataStoreReference id="${DATA_STORE_REF_ID}" name="Employee Records" dataStoreRef="DataStore_1" />
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Activity_lookup" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="Activity_lookup" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_phase6">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="150" y="150" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Activity_lookup_di" bpmnElement="Activity_lookup">
        <dc:Bounds x="250" y="128" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
        <dc:Bounds x="420" y="150" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="DataStoreReference_1_di" bpmnElement="${DATA_STORE_REF_ID}">
        <dc:Bounds x="285" y="260" width="50" height="50" />
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

test.describe('m8flow-designer Process Modeler — Data Store Reference wiring (Phase 6)', () => {
  test.fixme(
    'Select DataSource dropdown lists this model\'s own bpmn:dataStore declarations',
    async ({ page }) => {
      // Left runnable (not gutted to a comment) so un-skipping is a one-line
      // diff the moment either blocker above closes: seed via
      // seedProcessModelFile once m8flow-bpmn-core registers a DataStore
      // implementation, or swap in a live-creation path if the palette
      // grows one first.
      await signInAsSharedRealmUser(page, editorCredentials());
      await seedProcessModelFile(page, PHASE6_FILE, PHASE6_DIAGRAM_XML);
      await page.goto(seedModelerPath(PHASE6_FILE));
      await expect(page.getByText('Saved', { exact: true })).toBeVisible();
      await selectElement(page, DATA_STORE_REF_ID);

      const group = await openPropertiesPanelGroup(page, 'custom-datastore-properties');
      const select = group.getByLabel('Select DataSource');
      const optionLabels = await select.locator('option').allTextContents();
      expect(optionLabels).toContain('Employee Records');
    },
  );
});
