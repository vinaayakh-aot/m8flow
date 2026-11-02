"""Tiny BPMN 2.0 builder used to generate the perf-seed templates.

Diagrams are described in Python (nodes placed on a column/row grid, flows by
id) and rendered to BPMN XML with matching BPMN-DI, so every generated file
both runs on m8flow-core and renders in the m8flow-designer modeler.

Only constructs the m8flow host accepts and m8flow-core executes are offered
(see perf/README.md "BPMN coverage").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape, quoteattr

CELL_W = 170
CELL_H = 130
POOL_X = 120
POOL_HEADER = 30
LANE_HEADER = 30
ORIGIN_X = POOL_X + POOL_HEADER + LANE_HEADER

SIZES = {
    "task": (100, 80),
    "event": (36, 36),
    "gateway": (50, 50),
    "dataObject": (36, 50),
    "annotation": (160, 60),
}

TASK_TAGS = {"userTask", "manualTask", "scriptTask", "serviceTask", "businessRuleTask", "sendTask", "task"}
EVENT_TAGS = {"startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent"}
GATEWAY_TAGS = {"exclusiveGateway", "inclusiveGateway", "parallelGateway", "eventBasedGateway"}
CONTAINER_TAGS = {"subProcess", "transaction"}


def py(value: str) -> str:
    """Quote a Python string literal for an XML expression body."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class Node:
    id: str
    tag: str
    name: str | None
    col: float
    row: float
    parent: str | None = None
    event_def: str = ""
    extensions: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)
    span: tuple[float, float] = (1, 1)
    attached_to: str | None = None
    boundary_slot: int = 0

    @property
    def kind(self) -> str:
        if self.tag in TASK_TAGS:
            return "task"
        if self.tag in EVENT_TAGS:
            return "event"
        if self.tag in GATEWAY_TAGS:
            return "gateway"
        if self.tag in CONTAINER_TAGS:
            return "container"
        return self.tag


@dataclass
class Flow:
    id: str
    source: str
    target: str
    name: str | None = None
    condition: str | None = None
    default: bool = False


class Diagram:
    """One executable process (optionally inside a collaboration)."""

    def __init__(self, process_id: str, name: str, *, documentation: str = "") -> None:
        self.process_id = process_id
        self.name = name
        self.documentation = documentation
        self.nodes: dict[str, Node] = {}
        self.flows: list[Flow] = []
        self.lanes: list[tuple[str, str, float, float]] = []  # id, name, first row, last row
        self.messages: list[tuple[str, str]] = []
        self.signals: list[tuple[str, str]] = []
        self.errors: list[tuple[str, str, str]] = []
        self.escalations: list[tuple[str, str, str]] = []
        self.data_objects: list[tuple[str, str, str, float, float, str | None]] = []
        self.data_assocs: list[tuple[str, str, str, str]] = []  # id, kind(in/out), task, dataref
        self.annotations: list[tuple[str, str, float, float, str]] = []  # id, text, col, row, target
        self.groups: list[tuple[str, str, float, float, float, float]] = []  # id, label, col, row, cols, rows
        self.partner: tuple[str, str, str] | None = None  # participant id, name, process id
        self.message_flows: list[tuple[str, str, str, str, str | None]] = []  # id, name, src, tgt, messageRef
        self.io_inputs: list[tuple[str, str]] = []
        self.io_outputs: list[tuple[str, str]] = []
        self.rows = 1.0

    # ----------------------------------------------------------- declarations
    def lane(self, name: str, first_row: float, last_row: float) -> None:
        self.lanes.append((f"Lane_{name.lower().replace(' ', '_')}", name, first_row, last_row))
        self.rows = max(self.rows, last_row + 1)

    def message(self, mid: str, name: str) -> str:
        self.messages.append((mid, name))
        return mid

    def signal(self, sid: str, name: str) -> str:
        self.signals.append((sid, name))
        return sid

    def error(self, eid: str, name: str, code: str) -> str:
        self.errors.append((eid, name, code))
        return eid

    def escalation(self, eid: str, name: str, code: str) -> str:
        self.escalations.append((eid, name, code))
        return eid

    def partner_pool(self, participant_id: str, name: str) -> None:
        """A non-executable external participant drawn below the main pool."""
        self.partner = (participant_id, name, f"Process_{participant_id}_external")

    def message_flow(self, mfid: str, name: str, source: str, target: str, message_ref: str | None = None) -> None:
        self.message_flows.append((mfid, name, source, target, message_ref))

    def process_io(self, inputs: list[tuple[str, str]], outputs: list[tuple[str, str]]) -> None:
        self.io_inputs, self.io_outputs = inputs, outputs

    # ------------------------------------------------------------------ nodes
    def _add(self, node: Node) -> Node:
        if node.id in self.nodes:
            raise ValueError(f"duplicate id {node.id}")
        if node.id in {"Start", "End"}:
            raise ValueError("ids Start/End clash with SpiffWorkflow internals")
        self.nodes[node.id] = node
        return node

    def start(self, nid, name, col, row, *, timer: tuple[str, str] | None = None, parent=None):
        node = Node(nid, "startEvent", name, col, row, parent)
        if timer:
            node.event_def = _timer(*timer)
        return self._add(node)

    def end(self, nid, name, col, row, *, kind: str = "none", ref: str | None = None, parent=None):
        node = Node(nid, "endEvent", name, col, row, parent)
        node.event_def = _event_def(kind, ref)
        return self._add(node)

    def catch(self, nid, name, col, row, *, kind: str, ref: str | None = None, timer=None, condition=None, parent=None):
        node = Node(nid, "intermediateCatchEvent", name, col, row, parent)
        node.event_def = _event_def(kind, ref, timer=timer, condition=condition)
        return self._add(node)

    def throw(self, nid, name, col, row, *, kind: str, ref: str | None = None, parent=None):
        node = Node(nid, "intermediateThrowEvent", name, col, row, parent)
        node.event_def = _event_def(kind, ref)
        return self._add(node)

    def boundary(self, nid, name, attached_to, *, kind: str, ref=None, timer=None, interrupting=True, slot=0):
        host = self.nodes[attached_to]
        node = Node(nid, "boundaryEvent", name, host.col, host.row, host.parent, attached_to=attached_to, boundary_slot=slot)
        node.attrs["attachedToRef"] = attached_to
        if not interrupting:
            node.attrs["cancelActivity"] = "false"
        node.event_def = _event_def(kind, ref, timer=timer)
        return self._add(node)

    def gateway(self, nid, name, col, row, *, kind: str = "exclusive", parent=None):
        return self._add(Node(nid, f"{kind}Gateway", name, col, row, parent))

    def task(self, nid, name, col, row, *, tag: str = "task", parent=None, pre=None, post=None, instructions=None,
             loop: tuple[str, int] | None = None):
        node = Node(nid, tag, name, col, row, parent)
        if instructions:
            node.extensions.append(f"<spiffworkflow:instructionsForEndUser>{escape(instructions)}</spiffworkflow:instructionsForEndUser>")
        if pre:
            node.extensions.append(f"<spiffworkflow:preScript>{escape(pre)}</spiffworkflow:preScript>")
        if post:
            node.extensions.append(f"<spiffworkflow:postScript>{escape(post)}</spiffworkflow:postScript>")
        if loop:
            condition, maximum = loop
            node.body.append(
                f'<bpmn:standardLoopCharacteristics loopMaximum="{maximum}">'
                f'<bpmn:loopCondition xsi:type="bpmn:tFormalExpression">{escape(condition)}</bpmn:loopCondition>'
                "</bpmn:standardLoopCharacteristics>"
            )
        return self._add(node)

    def user(self, nid, name, col, row, *, form: str, **kw):
        node = self.task(nid, name, col, row, tag="userTask", **kw)
        node.extensions.insert(0, (
            "<spiffworkflow:properties>"
            f'<spiffworkflow:property name="formJsonSchemaFilename" value="{form}-schema.json" />'
            f'<spiffworkflow:property name="formUiSchemaFilename" value="{form}-uischema.json" />'
            "</spiffworkflow:properties>"
        ))
        return node

    def manual(self, nid, name, col, row, **kw):
        return self.task(nid, name, col, row, tag="manualTask", **kw)

    def script(self, nid, name, col, row, code: str, **kw):
        node = self.task(nid, name, col, row, tag="scriptTask", **kw)
        node.body.append(f"<bpmn:script>{escape(code)}</bpmn:script>")
        return node

    def rule(self, nid, name, col, row, decision_id: str, **kw):
        node = self.task(nid, name, col, row, tag="businessRuleTask", **kw)
        node.extensions.insert(0, f"<spiffworkflow:calledDecisionId>{decision_id}</spiffworkflow:calledDecisionId>")
        return node

    def service(self, nid, name, col, row, operator: str, params: dict[str, str | None], result: str, **kw):
        """params: name -> Python expression (None leaves it for the connector profile to fill)."""
        node = self.task(nid, name, col, row, tag="serviceTask", **kw)
        rendered = []
        for pid, expr in params.items():
            value = "" if expr is None else f" value={quoteattr(expr)}"
            rendered.append(f'<spiffworkflow:parameter id="{pid}" type="any"{value} />')
        node.extensions.insert(0, (
            f'<spiffworkflow:serviceTaskOperator id="{operator}" resultVariable="{result}">'
            f"<spiffworkflow:parameters>{''.join(rendered)}</spiffworkflow:parameters>"
            "</spiffworkflow:serviceTaskOperator>"
        ))
        return node

    def send(self, nid, name, col, row, message_ref: str, **kw):
        node = self.task(nid, name, col, row, tag="sendTask", **kw)
        node.attrs["messageRef"] = message_ref
        return node

    def container(self, nid, name, col, row, cols, rows, *, transaction=False, parent=None):
        node = Node(nid, "transaction" if transaction else "subProcess", name, col, row, parent, span=(cols, rows))
        return self._add(node)

    def flow(self, source: str, target: str, name: str | None = None, *, condition: str | None = None,
             default: bool = False, fid: str | None = None) -> None:
        self.flows.append(Flow(fid or f"Flow_{source}_{target}", source, target, name, condition, default))

    def data_object(self, did: str, name: str, col: float, row: float, parent: str | None = None) -> None:
        self.data_objects.append((did, name, f"{did}_ref", col, row, parent))

    def data_input(self, task: str, data_object: str) -> None:
        self.data_assocs.append((f"DataIn_{task}_{data_object}", "in", task, f"{data_object}_ref"))

    def data_output(self, task: str, data_object: str) -> None:
        self.data_assocs.append((f"DataOut_{task}_{data_object}", "out", task, f"{data_object}_ref"))

    def annotate(self, aid: str, text: str, col: float, row: float, target: str) -> None:
        self.annotations.append((aid, text, col, row, target))

    def group(self, gid: str, label: str, col: float, row: float, cols: float, rows: float) -> None:
        self.groups.append((gid, label, col, row, cols, rows))

    # ---------------------------------------------------------------- layout
    def _cell_origin(self, col: float, row: float) -> tuple[float, float]:
        return ORIGIN_X + col * CELL_W, self._pool_y() + row * CELL_H

    def _pool_y(self) -> float:
        return 60

    def bounds(self, nid: str) -> tuple[float, float, float, float]:
        node = self.nodes[nid]
        if node.tag == "boundaryEvent":
            hx, hy, _, hh = self.bounds(node.attached_to)
            w, h = SIZES["event"]
            return hx + 14 + node.boundary_slot * 44, hy + hh - h / 2, w, h
        cx0, cy0 = self._cell_origin(node.col, node.row)
        if node.kind == "container":
            cols, rows = node.span
            return cx0 + 8, cy0 + 8, cols * CELL_W - 16, rows * CELL_H - 16
        w, h = SIZES[node.kind]
        return cx0 + (CELL_W - w) / 2, cy0 + (CELL_H - h) / 2, w, h

    def _width_cols(self) -> float:
        right = 0.0
        for node in self.nodes.values():
            right = max(right, node.col + (node.span[0] if node.kind == "container" else 1))
        for _, _, col, _, _ in self.annotations:
            right = max(right, col + 1)
        return right

    def _waypoints(self, src: tuple[float, float, float, float], tgt: tuple[float, float, float, float],
                   from_bottom: bool) -> list[tuple[float, float]]:
        sx, sy, sw, sh = src
        tx, ty, tw, th = tgt
        tcy = ty + th / 2
        if from_bottom:
            bx = sx + sw / 2
            start = (bx, sy + sh)
            if tx <= bx <= tx + tw:
                return [start, (bx, ty)]
            return [start, (bx, tcy), (tx if tx > bx else tx + tw, tcy)]
        scy = sy + sh / 2
        start = (sx + sw, scy)
        end = (tx, tcy)
        if abs(scy - tcy) < 1 and tx >= sx + sw:
            return [start, end]
        if tx < sx + sw:  # target is left of (or overlapping) the source: route under it
            below = max(sy + sh, ty + th) + 25
            return [(sx + sw / 2, sy + sh), (sx + sw / 2, below), (tx + tw / 2, below), (tx + tw / 2, ty + th)]
        if tx - (sx + sw) < 60:  # target straight below/above: leave from top/bottom edge
            if tcy > scy:
                return [(sx + sw / 2, sy + sh), (sx + sw / 2, tcy), end]
            return [(sx + sw / 2, sy), (sx + sw / 2, tcy), end]
        mid = sx + sw + 25
        return [start, (mid, scy), (mid, tcy), end]

    # ---------------------------------------------------------------- render
    def to_xml(self) -> str:
        self._validate()
        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
                'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
                'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
                'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
                'xmlns:spiffworkflow="http://spiffworkflow.org/bpmn/schema/1.0/core" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                f'id="Definitions_{self.process_id}" targetNamespace="http://bpmn.io/schema/bpmn" '
                'exporter="m8flow perf-seed builder" exporterVersion="1">'
            ),
        ]
        lines.append(f'  <bpmn:collaboration id="Collaboration_{self.process_id}">')
        lines.append(f'    <bpmn:participant id="Participant_{self.process_id}" name={quoteattr(self.name)} processRef="{self.process_id}" />')
        if self.partner:
            pid, pname, pproc = self.partner
            lines.append(f'    <bpmn:participant id="{pid}" name={quoteattr(pname)} processRef="{pproc}" />')
        for mfid, name, src, tgt, mref in self.message_flows:
            mattr = f' messageRef="{mref}"' if mref else ""
            lines.append(f'    <bpmn:messageFlow id="{mfid}" name={quoteattr(name)} sourceRef="{src}" targetRef="{tgt}"{mattr} />')
        lines.append("  </bpmn:collaboration>")
        for mid, name in self.messages:
            lines.append(f'  <bpmn:message id="{mid}" name={quoteattr(name)} />')
        for sid, name in self.signals:
            lines.append(f'  <bpmn:signal id="{sid}" name={quoteattr(name)} />')
        for eid, name, code in self.errors:
            lines.append(f'  <bpmn:error id="{eid}" name={quoteattr(name)} errorCode="{code}" />')
        for eid, name, code in self.escalations:
            lines.append(f'  <bpmn:escalation id="{eid}" name={quoteattr(name)} escalationCode="{code}" />')
        for gid, label, *_ in self.groups:
            lines.append(f'  <bpmn:category id="Category_{gid}"><bpmn:categoryValue id="CategoryValue_{gid}" value={quoteattr(label)} /></bpmn:category>')

        lines.append(f'  <bpmn:process id="{self.process_id}" name={quoteattr(self.name)} isExecutable="true">')
        if self.documentation:
            lines.append(f"    <bpmn:documentation>{escape(self.documentation)}</bpmn:documentation>")
        if self.io_inputs or self.io_outputs:
            lines.append("    <bpmn:ioSpecification>")
            for did, name in self.io_inputs:
                lines.append(f'      <bpmn:dataInput id="{did}" name={quoteattr(name)} />')
            for did, name in self.io_outputs:
                lines.append(f'      <bpmn:dataOutput id="{did}" name={quoteattr(name)} />')
            lines.append("      <bpmn:inputSet>" + "".join(f"<bpmn:dataInputRefs>{d}</bpmn:dataInputRefs>" for d, _ in self.io_inputs) + "</bpmn:inputSet>")
            lines.append("      <bpmn:outputSet>" + "".join(f"<bpmn:dataOutputRefs>{d}</bpmn:dataOutputRefs>" for d, _ in self.io_outputs) + "</bpmn:outputSet>")
            lines.append("    </bpmn:ioSpecification>")
        if self.lanes:
            lines.append(f'    <bpmn:laneSet id="LaneSet_{self.process_id}">')
            for lid, lname, first, last in self.lanes:
                lines.append(f'      <bpmn:lane id="{lid}" name={quoteattr(lname)}>')
                for node in self.nodes.values():
                    if node.parent is None and first <= node.row <= last:
                        lines.append(f"        <bpmn:flowNodeRef>{node.id}</bpmn:flowNodeRef>")
                lines.append("      </bpmn:lane>")
            lines.append("    </bpmn:laneSet>")
        self._render_children(None, lines, "    ")
        for aid, text, _, _, target in self.annotations:
            lines.append(f'    <bpmn:textAnnotation id="{aid}"><bpmn:text>{escape(text)}</bpmn:text></bpmn:textAnnotation>')
            lines.append(f'    <bpmn:association id="Association_{aid}" sourceRef="{target}" targetRef="{aid}" />')
        for gid, *_ in self.groups:
            lines.append(f'    <bpmn:group id="{gid}" categoryValueRef="CategoryValue_{gid}" />')
        lines.append("  </bpmn:process>")
        if self.partner:
            lines.append(f'  <bpmn:process id="{self.partner[2]}" isExecutable="false" />')
        lines.extend(self._render_di())
        lines.append("</bpmn:definitions>")
        return "\n".join(lines) + "\n"

    def _render_children(self, parent: str | None, lines: list[str], ind: str) -> None:
        incoming: dict[str, list[str]] = {}
        outgoing: dict[str, list[str]] = {}
        for f in self.flows:
            outgoing.setdefault(f.source, []).append(f.id)
            incoming.setdefault(f.target, []).append(f.id)
        defaults = {f.source: f.id for f in self.flows if f.default}
        for node in [n for n in self.nodes.values() if n.parent == parent]:
            attrs = dict(node.attrs)
            if node.name:
                attrs = {"name": node.name, **attrs}
            if node.id in defaults:
                attrs["default"] = defaults[node.id]
            attr_text = "".join(f" {k}={quoteattr(v)}" for k, v in attrs.items())
            lines.append(f'{ind}<bpmn:{node.tag} id="{node.id}"{attr_text}>')
            if node.extensions:
                lines.append(f"{ind}  <bpmn:extensionElements>{''.join(node.extensions)}</bpmn:extensionElements>")
            for fid in incoming.get(node.id, []):
                lines.append(f"{ind}  <bpmn:incoming>{fid}</bpmn:incoming>")
            for fid in outgoing.get(node.id, []):
                lines.append(f"{ind}  <bpmn:outgoing>{fid}</bpmn:outgoing>")
            for assoc_id, kind, task, ref in self.data_assocs:
                if task == node.id and kind == "in":
                    lines.append(f'{ind}  <bpmn:dataInputAssociation id="{assoc_id}"><bpmn:sourceRef>{ref}</bpmn:sourceRef></bpmn:dataInputAssociation>')
            for assoc_id, kind, task, ref in self.data_assocs:
                if task == node.id and kind == "out":
                    lines.append(f'{ind}  <bpmn:dataOutputAssociation id="{assoc_id}"><bpmn:targetRef>{ref}</bpmn:targetRef></bpmn:dataOutputAssociation>')
            lines.extend(f"{ind}  {b}" for b in node.body)
            if node.kind == "container":
                self._render_children(node.id, lines, ind + "  ")
            if node.event_def:
                lines.append(f"{ind}  {node.event_def}")
            lines.append(f"{ind}</bpmn:{node.tag}>")
        for did, name, ref, _, _, dparent in self.data_objects:
            if dparent == parent:
                lines.append(f'{ind}<bpmn:dataObject id="{did}" />')
                lines.append(f'{ind}<bpmn:dataObjectReference id="{ref}" name={quoteattr(name)} dataObjectRef="{did}" />')
        for f in self.flows:
            if self.nodes[f.source].parent != parent:
                continue
            name = f" name={quoteattr(f.name)}" if f.name else ""
            if f.condition:
                lines.append(
                    f'{ind}<bpmn:sequenceFlow id="{f.id}"{name} sourceRef="{f.source}" targetRef="{f.target}">'
                    f'<bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">{escape(f.condition)}</bpmn:conditionExpression>'
                    "</bpmn:sequenceFlow>"
                )
            else:
                lines.append(f'{ind}<bpmn:sequenceFlow id="{f.id}"{name} sourceRef="{f.source}" targetRef="{f.target}" />')

    def _render_di(self) -> list[str]:
        out = [f'  <bpmndi:BPMNDiagram id="BPMNDiagram_{self.process_id}">',
               f'    <bpmndi:BPMNPlane id="BPMNPlane_{self.process_id}" bpmnElement="Collaboration_{self.process_id}">']
        pool_w = POOL_HEADER + LANE_HEADER + self._width_cols() * CELL_W + 20
        pool_y = self._pool_y()
        pool_h = self.rows * CELL_H
        out.append(_shape(f"Participant_{self.process_id}", POOL_X, pool_y, pool_w, pool_h, horizontal=True))
        for lid, _, first, last in self.lanes:
            out.append(_shape(lid, POOL_X + POOL_HEADER, pool_y + first * CELL_H, pool_w - POOL_HEADER,
                              (last - first + 1) * CELL_H, horizontal=True))
        if self.partner:
            out.append(_shape(self.partner[0], POOL_X, pool_y + pool_h + 60, pool_w, 100, horizontal=True))
        for gid, _, col, row, cols, rows in self.groups:
            x, y = self._cell_origin(col, row)
            out.append(_shape(gid, x + 2, y + 2, cols * CELL_W - 4, rows * CELL_H - 4))
        # containers first so their children draw on top
        ordered = sorted(self.nodes.values(), key=lambda n: (n.kind != "container", n.tag == "boundaryEvent"))
        for node in ordered:
            x, y, w, h = self.bounds(node.id)
            out.append(_shape(node.id, x, y, w, h, expanded=node.kind == "container", label=node.kind in {"event", "gateway"} and bool(node.name)))
        for did, _, ref, col, row, _ in self.data_objects:
            x, y = self._cell_origin(col, row)
            w, h = SIZES["dataObject"]
            out.append(_shape(ref, x + (CELL_W - w) / 2, y + (CELL_H - h) / 2, w, h, label=True))
        for aid, _, col, row, _ in self.annotations:
            x, y = self._cell_origin(col, row)
            w, h = SIZES["annotation"]
            out.append(_shape(aid, x + 5, y + (CELL_H - h) / 2, w, h))
        for f in self.flows:
            src = self.nodes[f.source]
            pts = self._waypoints(self.bounds(f.source), self.bounds(f.target), src.tag == "boundaryEvent")
            out.append(_edge(f.id, pts))
        data_bounds = {}
        for did, _, ref, col, row, _ in self.data_objects:
            x, y = self._cell_origin(col, row)
            w, h = SIZES["dataObject"]
            data_bounds[ref] = (x + (CELL_W - w) / 2, y + (CELL_H - h) / 2, w, h)
        for assoc_id, kind, task, ref in self.data_assocs:
            tb, db = self.bounds(task), data_bounds[ref]
            tc = (tb[0] + tb[2] / 2, tb[1] + tb[3] / 2)
            dc = (db[0] + db[2] / 2, db[1] + db[3] / 2)
            pts = [dc, tc] if kind == "in" else [tc, dc]
            out.append(_edge(assoc_id, pts))
        for aid, _, col, row, target in self.annotations:
            tb = self.bounds(target)
            x, y = self._cell_origin(col, row)
            out.append(_edge(f"Association_{aid}", [(tb[0] + tb[2] / 2, tb[1]), (x + 5, y + CELL_H / 2)]))
        for mfid, _, src, tgt, _ in self.message_flows:
            sb = self._any_bounds(src)
            tb = self._any_bounds(tgt)
            if sb[1] < tb[1]:
                pts = [(sb[0] + sb[2] / 2, sb[1] + sb[3]), (sb[0] + sb[2] / 2, tb[1])]
            else:
                pts = [(tb[0] + tb[2] / 2, sb[1]), (tb[0] + tb[2] / 2, tb[1] + tb[3])]
            out.append(_edge(mfid, pts))
        out.append("    </bpmndi:BPMNPlane>")
        out.append("  </bpmndi:BPMNDiagram>")
        return out

    def _any_bounds(self, ref: str) -> tuple[float, float, float, float]:
        if ref in self.nodes:
            return self.bounds(ref)
        pool_w = POOL_HEADER + LANE_HEADER + self._width_cols() * CELL_W + 20
        return POOL_X, self._pool_y() + self.rows * CELL_H + 60, pool_w, 100

    def _validate(self) -> None:
        ids = set(self.nodes)
        for f in self.flows:
            for ref in (f.source, f.target):
                if ref not in ids:
                    raise ValueError(f"flow {f.id} references unknown node {ref}")
            if self.nodes[f.source].parent != self.nodes[f.target].parent:
                raise ValueError(f"flow {f.id} crosses a sub-process boundary")
        for node in self.nodes.values():
            if node.tag == "boundaryEvent":
                continue
            if node.tag != "startEvent" and node.id not in {f.target for f in self.flows}:
                raise ValueError(f"node {node.id} has no incoming flow")
            if node.tag != "endEvent" and node.id not in {f.source for f in self.flows}:
                raise ValueError(f"node {node.id} has no outgoing flow")


def _timer(kind: str, expr: str) -> str:
    tag = {"duration": "timeDuration", "date": "timeDate", "cycle": "timeCycle"}[kind]
    return (f'<bpmn:timerEventDefinition><bpmn:{tag} xsi:type="bpmn:tFormalExpression">{escape(expr)}'
            f"</bpmn:{tag}></bpmn:timerEventDefinition>")


def _event_def(kind: str, ref: str | None = None, *, timer=None, condition=None) -> str:
    if kind == "none":
        return ""
    if kind == "timer":
        return _timer(*timer)
    if kind == "conditional":
        return (f'<bpmn:conditionalEventDefinition><bpmn:condition xsi:type="bpmn:tFormalExpression">'
                f"{escape(condition)}</bpmn:condition></bpmn:conditionalEventDefinition>")
    if kind in {"terminate", "cancel"}:
        return f"<bpmn:{kind}EventDefinition />"
    ref_attr = {"signal": "signalRef", "error": "errorRef", "escalation": "escalationRef"}[kind]
    return f'<bpmn:{kind}EventDefinition {ref_attr}="{ref}" />'


def _shape(element: str, x, y, w, h, *, horizontal=False, expanded=False, label=False) -> str:
    extra = ' isHorizontal="true"' if horizontal else ""
    extra += ' isExpanded="true"' if expanded else ""
    label_xml = ""
    if label:
        label_xml = f'<bpmndi:BPMNLabel><dc:Bounds x="{x - 30:.0f}" y="{y + h + 4:.0f}" width="{w + 60:.0f}" height="27" /></bpmndi:BPMNLabel>'
    return (f'      <bpmndi:BPMNShape id="{element}_di" bpmnElement="{element}"{extra}>'
            f'<dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" />{label_xml}</bpmndi:BPMNShape>')


def _edge(element: str, pts: list[tuple[float, float]]) -> str:
    wps = "".join(f'<di:waypoint x="{x:.0f}" y="{y:.0f}" />' for x, y in pts)
    return f'      <bpmndi:BPMNEdge id="{element}_di" bpmnElement="{element}">{wps}</bpmndi:BPMNEdge>'
