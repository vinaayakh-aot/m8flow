// PROTOTYPE — throwaway. A small hand-authored process exercising a few
// spiffworkflow BPMN extensions (InstructionsForEndUser, PreScript/PostScript,
// ServiceTaskOperator) so each variant can prove the properties panel still
// authors real engine-consumed fields, not just stock BPMN.
export const SAMPLE_BPMN_XML = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:spiffworkflow="http://spiffworkflow.org/bpmn/schema/1.0/core"
                  id="Definitions_prototype"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_n8n_prototype" name="Onboarding request" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" name="Start">
      <bpmn:outgoing>Flow_1</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:userTask id="UserTask_1" name="Review request">
      <bpmn:extensionElements>
        <spiffworkflow:InstructionsForEndUser>Please review the request details and approve or reject.</spiffworkflow:InstructionsForEndUser>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_1</bpmn:incoming>
      <bpmn:outgoing>Flow_2</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:scriptTask id="ScriptTask_1" name="Normalize data" scriptFormat="python">
      <bpmn:extensionElements>
        <spiffworkflow:PreScript>data = request.get('payload', {})</spiffworkflow:PreScript>
        <spiffworkflow:PostScript>result = {'normalized': True}</spiffworkflow:PostScript>
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_2</bpmn:incoming>
      <bpmn:outgoing>Flow_3</bpmn:outgoing>
    </bpmn:scriptTask>
    <bpmn:exclusiveGateway id="Gateway_1" name="Approved?">
      <bpmn:incoming>Flow_3</bpmn:incoming>
      <bpmn:outgoing>Flow_4</bpmn:outgoing>
      <bpmn:outgoing>Flow_5</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:serviceTask id="ServiceTask_1" name="Send welcome email">
      <bpmn:extensionElements>
        <spiffworkflow:ServiceTaskOperator id="email/send_email" resultVariable="email_result" />
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_4</bpmn:incoming>
      <bpmn:outgoing>Flow_6</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:serviceTask id="ServiceTask_2" name="Log rejection">
      <bpmn:extensionElements>
        <spiffworkflow:ServiceTaskOperator id="log/write" resultVariable="log_result" />
      </bpmn:extensionElements>
      <bpmn:incoming>Flow_5</bpmn:incoming>
      <bpmn:outgoing>Flow_7</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:endEvent id="EndEvent_1" name="Done">
      <bpmn:incoming>Flow_6</bpmn:incoming>
      <bpmn:incoming>Flow_7</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="UserTask_1" />
    <bpmn:sequenceFlow id="Flow_2" sourceRef="UserTask_1" targetRef="ScriptTask_1" />
    <bpmn:sequenceFlow id="Flow_3" sourceRef="ScriptTask_1" targetRef="Gateway_1" />
    <bpmn:sequenceFlow id="Flow_4" name="Yes" sourceRef="Gateway_1" targetRef="ServiceTask_1" />
    <bpmn:sequenceFlow id="Flow_5" name="No" sourceRef="Gateway_1" targetRef="ServiceTask_2" />
    <bpmn:sequenceFlow id="Flow_6" sourceRef="ServiceTask_1" targetRef="EndEvent_1" />
    <bpmn:sequenceFlow id="Flow_7" sourceRef="ServiceTask_2" targetRef="EndEvent_1" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_n8n_prototype">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="120" y="220" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="UserTask_1_di" bpmnElement="UserTask_1">
        <dc:Bounds x="220" y="198" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="ScriptTask_1_di" bpmnElement="ScriptTask_1">
        <dc:Bounds x="380" y="198" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="Gateway_1_di" bpmnElement="Gateway_1" isMarkerVisible="true">
        <dc:Bounds x="540" y="213" width="50" height="50" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="ServiceTask_1_di" bpmnElement="ServiceTask_1">
        <dc:Bounds x="650" y="100" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="ServiceTask_2_di" bpmnElement="ServiceTask_2">
        <dc:Bounds x="650" y="320" width="100" height="80" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="EndEvent_1_di" bpmnElement="EndEvent_1">
        <dc:Bounds x="820" y="220" width="36" height="36" />
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="Flow_1_di" bpmnElement="Flow_1">
        <di:waypoint x="156" y="238" />
        <di:waypoint x="220" y="238" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_2_di" bpmnElement="Flow_2">
        <di:waypoint x="320" y="238" />
        <di:waypoint x="380" y="238" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_3_di" bpmnElement="Flow_3">
        <di:waypoint x="480" y="238" />
        <di:waypoint x="540" y="238" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_4_di" bpmnElement="Flow_4">
        <di:waypoint x="565" y="213" />
        <di:waypoint x="565" y="140" />
        <di:waypoint x="650" y="140" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_5_di" bpmnElement="Flow_5">
        <di:waypoint x="565" y="263" />
        <di:waypoint x="565" y="360" />
        <di:waypoint x="650" y="360" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_6_di" bpmnElement="Flow_6">
        <di:waypoint x="750" y="140" />
        <di:waypoint x="790" y="140" />
        <di:waypoint x="790" y="238" />
        <di:waypoint x="820" y="238" />
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="Flow_7_di" bpmnElement="Flow_7">
        <di:waypoint x="750" y="360" />
        <di:waypoint x="790" y="360" />
        <di:waypoint x="790" y="238" />
        <di:waypoint x="820" y="238" />
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
`;

// Node types offered by the "add node" affordance in each variant. Kept as
// data so all three variants (and the picker UIs) share one source of truth.
export type PaletteEntry = {
  type: string;
  label: string;
  category: 'Tasks' | 'Gateways' | 'Events';
};

export const PALETTE_ENTRIES: PaletteEntry[] = [
  { type: 'bpmn:UserTask', label: 'User task', category: 'Tasks' },
  { type: 'bpmn:ScriptTask', label: 'Script task', category: 'Tasks' },
  { type: 'bpmn:ServiceTask', label: 'Service task', category: 'Tasks' },
  { type: 'bpmn:ExclusiveGateway', label: 'Exclusive gateway', category: 'Gateways' },
  { type: 'bpmn:ParallelGateway', label: 'Parallel gateway', category: 'Gateways' },
  { type: 'bpmn:IntermediateThrowEvent', label: 'Intermediate event', category: 'Events' },
  { type: 'bpmn:EndEvent', label: 'End event', category: 'Events' },
];
