// PROTOTYPE — throwaway. Small helpers around bpmn-js's public Modeling
// service, shared by whichever variant needs to create a node — the affordance
// that triggers them (hover-on-connection, drag-from-rail, command palette)
// is what's actually being varied.

// Creates `type` at `{x, y}` (diagram coordinates) as a free-floating shape.
export function createShapeAt(modeler: any, type: string, x: number, y: number) {
  const modeling = modeler.get('modeling');
  const elementFactory = modeler.get('elementFactory');
  const canvas = modeler.get('canvas');

  const shape = elementFactory.createShape({ type });
  return modeling.createShape(
    shape,
    { x, y },
    canvas.getRootElement(),
  );
}

// Splits a sequence flow, inserting a freshly created node at its midpoint —
// the n8n "click the + on a wire" move. Implemented with the same public
// createShape/createConnection/removeConnection calls the stock palette uses
// internally, just driven from our own UI instead of theirs.
export function insertShapeOnConnection(modeler: any, connection: any, type: string) {
  const modeling = modeler.get('modeling');
  const canvas = modeler.get('canvas');
  const waypoints = connection.waypoints;
  const mid = waypoints[Math.floor(waypoints.length / 2)];

  const { source, target, parent } = connection;
  modeling.removeConnection(connection);

  const shape = createShapeAt(modeler, type, mid.x, mid.y);

  modeling.createConnection(
    source,
    shape,
    { type: 'bpmn:SequenceFlow' },
    parent ?? canvas.getRootElement(),
  );
  modeling.createConnection(
    shape,
    target,
    { type: 'bpmn:SequenceFlow' },
    parent ?? canvas.getRootElement(),
  );

  return shape;
}

// Converts a browser client position to diagram coordinates, accounting for
// the canvas container's current pan/zoom — needed by both the drag-and-drop
// rail (variant B) and the command palette's "insert near last click" (C).
export function clientToDiagramPosition(
  modeler: any,
  containerEl: HTMLElement,
  clientX: number,
  clientY: number,
) {
  const canvas = modeler.get('canvas');
  const viewbox = canvas.viewbox();
  const rect = containerEl.getBoundingClientRect();
  return {
    x: (clientX - rect.left) / viewbox.scale + viewbox.x,
    y: (clientY - rect.top) / viewbox.scale + viewbox.y,
  };
}

export function elementLabel(element: any): string | null {
  if (!element) return null;
  const bo = element.businessObject;
  return bo?.name || element.type?.replace('bpmn:', '') || element.id;
}
