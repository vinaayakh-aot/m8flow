// PROTOTYPE — throwaway.
//
// Variant A — "Inline add on connection, accordion panel"
// Primary affordance: hover any wire, a "+" appears at its midpoint; click it
// to search-and-insert a node splice right into that flow (n8n's own
// canonical move). No persistent palette/rail at all — the canvas is empty
// chrome except a minimal zoom toolbar. The properties panel is untouched
// stock bpmn-js-properties-panel behaviour (collapsible group accordion),
// just restyled — this is the "cheapest" of the three, and the baseline to
// judge the other two against.
import React, { useEffect, useRef, useState } from 'react';
import { Layout } from '../shared/Layout';
import { useN8nModeler } from '../shared/useN8nModeler';
import { insertShapeOnConnection, elementLabel } from '../shared/canvasActions';
import { PALETTE_ENTRIES } from '../shared/sampleProcess';
import './VariantA.css';

export function VariantA() {
  const { canvasRef, panelRef, modeler, selected } = useN8nModeler();
  const [picker, setPicker] = useState<{ connection: any; x: number; y: number } | null>(null);
  const [query, setQuery] = useState('');
  const overlayIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!modeler) return undefined;
    const overlays = modeler.get('overlays');
    const canvas = modeler.get('canvas');

    function clearAddButton() {
      if (overlayIdRef.current) {
        overlays.remove(overlayIdRef.current);
        overlayIdRef.current = null;
      }
    }

    function onHover(event: any) {
      clearAddButton();
      const element = event.element;
      if (!element || element.type !== 'bpmn:SequenceFlow') return;
      const mid = element.waypoints[Math.floor(element.waypoints.length / 2)];
      const btn = document.createElement('button');
      btn.className = 'n8n-add-btn';
      btn.type = 'button';
      btn.textContent = '+';
      btn.onmousedown = (e) => e.stopPropagation();
      btn.onclick = (e) => {
        e.stopPropagation();
        const viewbox = canvas.viewbox();
        const rect = (canvasRef.current as HTMLDivElement).getBoundingClientRect();
        setPicker({
          connection: element,
          x: rect.left + (mid.x - viewbox.x) * viewbox.scale,
          y: rect.top + (mid.y - viewbox.y) * viewbox.scale,
        });
        setQuery('');
      };
      overlayIdRef.current = overlays.add(element, {
        position: { left: mid.x - 12, top: mid.y - 12 },
        html: btn,
      });
    }

    modeler.on('element.hover', onHover);
    return () => {
      modeler.off('element.hover', onHover);
      clearAddButton();
    };
  }, [modeler, canvasRef]);

  function choose(type: string) {
    if (!picker) return;
    insertShapeOnConnection(modeler, picker.connection, type);
    setPicker(null);
  }

  const filtered = PALETTE_ENTRIES.filter((entry) =>
    entry.label.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <Layout
      canvasRef={canvasRef}
      panelRef={panelRef}
      selectedLabel={elementLabel(selected)}
      canvasOverlay={
        <>
          <div className="n8n-toolbar">
            <button type="button" onClick={() => modeler?.get('zoomScroll').stepZoom(1)}>
              +
            </button>
            <button type="button" onClick={() => modeler?.get('zoomScroll').stepZoom(-1)}>
              –
            </button>
            <button
              type="button"
              onClick={() => modeler?.get('canvas').zoom('fit-viewport')}
            >
              ⤢
            </button>
          </div>
          {picker && (
            <div
              className="n8n-inline-picker"
              style={{ left: picker.x - 110, top: picker.y + 16 }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <input
                autoFocus
                className="n8n-search-input"
                placeholder="Add a node…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <div className="n8n-inline-picker-list">
                {filtered.map((entry) => (
                  <div
                    key={entry.type}
                    className="n8n-node-item"
                    onClick={() => choose(entry.type)}
                  >
                    {entry.label}
                  </div>
                ))}
                {filtered.length === 0 && (
                  <div className="n8n-node-item n8n-node-item--empty">No matches</div>
                )}
              </div>
              <button
                type="button"
                className="n8n-inline-picker-close"
                onClick={() => setPicker(null)}
              >
                Cancel
              </button>
            </div>
          )}
        </>
      }
    />
  );
}
