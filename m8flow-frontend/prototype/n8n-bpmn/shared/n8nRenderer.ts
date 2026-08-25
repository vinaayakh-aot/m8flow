// PROTOTYPE — throwaway. A bpmn-js custom-renderer module (the standard
// `BaseRenderer` extension recipe) that reskins task/gateway/event shapes and
// sequence-flow connections toward an n8n look, while delegating anything it
// doesn't override (pools, lanes, data objects, message flows, ...) to the
// stock BpmnRenderer. This is a visual skin only — element types, moddle
// extensions, and the exported XML are untouched.
import BaseRenderer from 'diagram-js/lib/draw/BaseRenderer';
import {
  append as svgAppend,
  attr as svgAttr,
  create as svgCreate,
} from 'tiny-svg';
import { is } from 'bpmn-js/lib/util/ModelUtil';

const HIGH_PRIORITY = 1500;
const TASK_RADIUS = 10;

// One accent colour per task flavour so the "what kind of node is this" cue
// n8n gives via icon+colour survives even in our simplified shape language.
const TASK_COLORS: Record<string, string> = {
  'bpmn:UserTask': '#7c3aed',
  'bpmn:ScriptTask': '#0891b2',
  'bpmn:ServiceTask': '#2563eb',
  'bpmn:ManualTask': '#ea580c',
  'bpmn:BusinessRuleTask': '#059669',
  'bpmn:Task': '#64748b',
};

const TASK_LABELS: Record<string, string> = {
  'bpmn:UserTask': 'User task',
  'bpmn:ScriptTask': 'Script',
  'bpmn:ServiceTask': 'Service',
  'bpmn:ManualTask': 'Manual',
  'bpmn:BusinessRuleTask': 'Rule',
  'bpmn:Task': 'Task',
};

function taskColor(element: any): string {
  return TASK_COLORS[element.type] ?? TASK_COLORS['bpmn:Task'];
}

function taskKind(element: any): string {
  return TASK_LABELS[element.type] ?? TASK_LABELS['bpmn:Task'];
}

// Smooths bpmn-js's (mostly orthogonal) routed waypoints into a single
// n8n-style bezier path, without needing to know how many bends it has.
function smoothPath(waypoints: Array<{ x: number; y: number }>): string {
  if (waypoints.length < 2) return '';
  let d = `M ${waypoints[0].x} ${waypoints[0].y}`;
  for (let i = 1; i < waypoints.length; i += 1) {
    const p0 = waypoints[i - 1];
    const p1 = waypoints[i];
    const dx = (p1.x - p0.x) * 0.5;
    d += ` C ${p0.x + dx} ${p0.y}, ${p1.x - dx} ${p1.y}, ${p1.x} ${p1.y}`;
  }
  return d;
}

function arrowHead(p0: { x: number; y: number }, p1: { x: number; y: number }): string {
  const angle = Math.atan2(p1.y - p0.y, p1.x - p0.x);
  const size = 7;
  const back = angle + Math.PI;
  const a1 = back - 0.45;
  const a2 = back + 0.45;
  const x1 = p1.x + size * Math.cos(a1);
  const y1 = p1.y + size * Math.sin(a1);
  const x2 = p1.x + size * Math.cos(a2);
  const y2 = p1.y + size * Math.sin(a2);
  return `M ${p1.x} ${p1.y} L ${x1} ${y1} L ${x2} ${y2} Z`;
}

export default function N8nRenderer(this: any, eventBus: any, bpmnRenderer: any) {
  BaseRenderer.call(this, eventBus, HIGH_PRIORITY);

  this.canRender = function canRender() {
    return true;
  };

  this.drawShape = function drawShape(parentNode: any, element: any) {
    if (is(element, 'bpmn:Task')) {
      const color = taskColor(element);
      const rect = svgCreate('rect');
      svgAttr(rect, {
        x: 0,
        y: 0,
        width: element.width,
        height: element.height,
        rx: TASK_RADIUS,
        ry: TASK_RADIUS,
        fill: '#ffffff',
        stroke: color,
        'stroke-width': 1.5,
        filter: 'drop-shadow(0 1px 2px rgba(15, 23, 42, 0.12))',
      });
      svgAppend(parentNode, rect);

      const accent = svgCreate('rect');
      svgAttr(accent, {
        x: 0,
        y: 0,
        width: 6,
        height: element.height,
        rx: TASK_RADIUS,
        fill: color,
      });
      svgAppend(parentNode, accent);
      // Square off the accent bar's right edge so only the outer corners stay rounded.
      const maskFix = svgCreate('rect');
      svgAttr(maskFix, { x: 3, y: 0, width: 3, height: element.height, fill: color });
      svgAppend(parentNode, maskFix);

      const kind = svgCreate('text');
      svgAttr(kind, { x: 16, y: 16, fill: color, 'font-size': 9, 'font-weight': 700 });
      kind.textContent = taskKind(element).toUpperCase();
      svgAppend(parentNode, kind);

      return rect;
    }

    if (is(element, 'bpmn:Gateway')) {
      const half = element.width / 2;
      const cy = element.height / 2;
      const diamond = svgCreate('polygon');
      svgAttr(diamond, {
        points: `${half},0 ${element.width},${cy} ${half},${element.height} 0,${cy}`,
        fill: '#fffbeb',
        stroke: '#d97706',
        'stroke-width': 1.5,
      });
      svgAppend(parentNode, diamond);
      return diamond;
    }

    if (is(element, 'bpmn:Event')) {
      const r = element.width / 2;
      const isEnd = is(element, 'bpmn:EndEvent');
      const isStart = is(element, 'bpmn:StartEvent');
      const color = isEnd ? '#dc2626' : isStart ? '#16a34a' : '#d97706';
      const circle = svgCreate('circle');
      svgAttr(circle, {
        cx: r,
        cy: r,
        r: r - 1,
        fill: '#ffffff',
        stroke: color,
        'stroke-width': isEnd ? 3 : 2,
      });
      svgAppend(parentNode, circle);
      return circle;
    }

    // Pools, lanes, data objects/stores, subprocesses, etc: unchanged.
    return bpmnRenderer.drawShape(parentNode, element);
  };

  this.drawConnection = function drawConnection(parentNode: any, element: any) {
    if (is(element, 'bpmn:SequenceFlow')) {
      const waypoints = element.waypoints;
      const path = svgCreate('path');
      svgAttr(path, {
        d: smoothPath(waypoints),
        fill: 'none',
        stroke: '#94a3b8',
        'stroke-width': 2,
      });
      svgAppend(parentNode, path);

      const head = svgCreate('path');
      svgAttr(head, {
        d: arrowHead(waypoints[waypoints.length - 2], waypoints[waypoints.length - 1]),
        fill: '#94a3b8',
      });
      svgAppend(parentNode, head);

      return path;
    }

    return bpmnRenderer.drawConnection(parentNode, element);
  };

  // Delegate hit-testing / bendpoint geometry to the stock renderer so
  // selection, dragging and reconnecting keep working unmodified.
  this.getShapePath = function getShapePath(shape: any) {
    return bpmnRenderer.getShapePath(shape);
  };

  this.getConnectionPath = function getConnectionPath(connection: any) {
    return bpmnRenderer.getConnectionPath(connection);
  };
}

N8nRenderer.$inject = ['eventBus', 'bpmnRenderer'];

export const n8nRendererModule = {
  __init__: ['n8nRenderer'],
  n8nRenderer: ['type', N8nRenderer],
};
