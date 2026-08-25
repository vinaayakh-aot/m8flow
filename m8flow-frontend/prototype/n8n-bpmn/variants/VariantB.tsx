// PROTOTYPE — throwaway.
//
// Variant B — "Floating searchable rail + tabbed panel"
// Primary affordance: a collapsible left rail (toggled by an edge tab) lists
// every node type, searchable, dragged onto the canvas at the drop point.
// The properties panel trades the stock accordion for tabs — General /
// Behaviour / Advanced — that show/hide the same underlying provider groups,
// so the information hierarchy itself is the thing being judged here.
import React, { useEffect, useRef, useState } from 'react';
import { Layout } from '../shared/Layout';
import { useN8nModeler } from '../shared/useN8nModeler';
import { createShapeAt, clientToDiagramPosition, elementLabel } from '../shared/canvasActions';
import { PALETTE_ENTRIES, PaletteEntry } from '../shared/sampleProcess';
import './VariantB.css';

const TABS = ['General', 'Behaviour', 'Advanced'] as const;
type Tab = (typeof TABS)[number];

// Keyword classification, not an exact id allowlist — robust to not knowing
// bpmn-js-properties-panel's/spiffworkflow's exact internal group ids.
function classifyGroup(groupId: string): Tab {
  const id = groupId.toLowerCase();
  if (id.includes('general') || id.includes('documentation') || id.includes('id')) {
    return 'General';
  }
  if (
    id.includes('script') ||
    id.includes('service') ||
    id.includes('message') ||
    id.includes('loop') ||
    id.includes('io') ||
    id.includes('condition') ||
    id.includes('call')
  ) {
    return 'Behaviour';
  }
  return 'Advanced';
}

export function VariantB() {
  const { canvasRef, panelRef, modeler, selected } = useN8nModeler();
  const [railOpen, setRailOpen] = useState(true);
  const [query, setQuery] = useState('');
  const [tab, setTab] = useState<Tab>('General');

  // Drag-and-drop from the rail onto the canvas.
  useEffect(() => {
    if (!modeler || !canvasRef.current) return undefined;
    const container = canvasRef.current;

    function onDragOver(event: DragEvent) {
      event.preventDefault();
    }
    function onDrop(event: DragEvent) {
      event.preventDefault();
      const type = event.dataTransfer?.getData('text/plain');
      if (!type) return;
      const { x, y } = clientToDiagramPosition(modeler, container, event.clientX, event.clientY);
      createShapeAt(modeler, type, x, y);
    }

    container.addEventListener('dragover', onDragOver);
    container.addEventListener('drop', onDrop);
    return () => {
      container.removeEventListener('dragover', onDragOver);
      container.removeEventListener('drop', onDrop);
    };
  }, [modeler, canvasRef]);

  // Tabbed panel: show only groups matching the active tab. Re-applied on a
  // timer-debounced MutationObserver since bpmn-js-properties-panel rebuilds
  // its DOM on every selection/element change.
  useEffect(() => {
    if (!panelRef.current) return undefined;
    const panelEl = panelRef.current;

    function apply() {
      panelEl
        .querySelectorAll<HTMLElement>('.bio-properties-panel-group[data-group-id]')
        .forEach((group) => {
          const id = group.getAttribute('data-group-id') ?? '';
          group.style.display = classifyGroup(id) === tab ? '' : 'none';
        });
    }

    apply();
    const observer = new MutationObserver(() => apply());
    observer.observe(panelEl, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [panelRef, tab, selected]);

  const grouped = PALETTE_ENTRIES.filter((entry) =>
    entry.label.toLowerCase().includes(query.toLowerCase()),
  ).reduce<Record<string, PaletteEntry[]>>((acc, entry) => {
    (acc[entry.category] ??= []).push(entry);
    return acc;
  }, {});

  return (
    <Layout
      canvasRef={canvasRef}
      panelRef={panelRef}
      selectedLabel={elementLabel(selected)}
      panelHeader={
        <>
          <span className="n8n-panel-title">{elementLabel(selected) ?? 'Nothing selected'}</span>
          <div className="n8n-tabs">
            {TABS.map((t) => (
              <button
                key={t}
                type="button"
                className={t === tab ? 'n8n-tab n8n-tab--active' : 'n8n-tab'}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
        </>
      }
      canvasOverlay={
        <>
          <button
            type="button"
            className="n8n-rail-toggle"
            style={{ left: railOpen ? 268 : 8 }}
            onClick={() => setRailOpen((v) => !v)}
          >
            {railOpen ? '‹' : '›'}
          </button>
          {railOpen && (
            <div className="n8n-rail">
              <input
                className="n8n-search-input"
                placeholder="Search nodes…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <div className="n8n-rail-list">
                {Object.entries(grouped).map(([category, entries]) => (
                  <div key={category}>
                    <div className="n8n-node-item-category">{category}</div>
                    {entries.map((entry) => (
                      <div
                        key={entry.type}
                        className="n8n-node-item"
                        draggable
                        onDragStart={(e) => e.dataTransfer.setData('text/plain', entry.type)}
                      >
                        {entry.label}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      }
    />
  );
}
