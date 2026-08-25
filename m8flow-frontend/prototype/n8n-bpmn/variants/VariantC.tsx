// PROTOTYPE — throwaway.
//
// Variant C — "Command palette + flat panel"
// Primary affordance: no palette, no rail — a single floating "+" (or
// Cmd/Ctrl+K) opens a searchable command palette, keyboard-navigable, that
// drops the chosen node at the last place you clicked on the canvas. Closest
// to the interaction idea (not the library) in the joint-demos AI workflow
// builder reference. The properties panel drops the accordion entirely —
// every group forced open, flat single column — the opposite hierarchy
// choice from variant B's tabs.
import React, { useEffect, useRef, useState } from 'react';
import { Layout } from '../shared/Layout';
import { useN8nModeler } from '../shared/useN8nModeler';
import { createShapeAt, clientToDiagramPosition, elementLabel } from '../shared/canvasActions';
import { PALETTE_ENTRIES } from '../shared/sampleProcess';
import './VariantC.css';

export function VariantC() {
  const { canvasRef, panelRef, modeler, selected } = useN8nModeler();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const lastPositionRef = useRef({ x: 300, y: 300 });

  // Track the last clicked canvas point so the palette knows where to drop.
  useEffect(() => {
    if (!modeler || !canvasRef.current) return undefined;
    const container = canvasRef.current;
    function onClick(event: MouseEvent) {
      lastPositionRef.current = clientToDiagramPosition(
        modeler,
        container,
        event.clientX,
        event.clientY,
      );
    }
    container.addEventListener('click', onClick);
    return () => container.removeEventListener('click', onClick);
  }, [modeler, canvasRef]);

  // Cmd/Ctrl+K opens the palette from anywhere.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen(true);
        setQuery('');
        setCursor(0);
      }
      if (event.key === 'Escape') setOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Flat panel: force every group open, every time the panel rebuilds.
  useEffect(() => {
    if (!panelRef.current) return undefined;
    const panelEl = panelRef.current;

    function forceOpen() {
      panelEl
        .querySelectorAll<HTMLElement>('.bio-properties-panel-group')
        .forEach((group) => {
          if (!group.classList.contains('open')) {
            const header = group.querySelector<HTMLElement>(
              '.bio-properties-panel-group-header-button, .bio-properties-panel-group-header',
            );
            header?.click();
          }
        });
    }

    forceOpen();
    const observer = new MutationObserver(() => forceOpen());
    observer.observe(panelEl, { childList: true, subtree: true, attributes: true });
    return () => observer.disconnect();
  }, [panelRef, selected]);

  const filtered = PALETTE_ENTRIES.filter((entry) =>
    entry.label.toLowerCase().includes(query.toLowerCase()),
  );

  function choose(type: string) {
    const { x, y } = lastPositionRef.current;
    createShapeAt(modeler, type, x, y);
    setOpen(false);
  }

  function onPaletteKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setCursor((c) => Math.min(c + 1, filtered.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (event.key === 'Enter' && filtered[cursor]) {
      choose(filtered[cursor].type);
    }
  }

  return (
    <Layout
      canvasRef={canvasRef}
      panelRef={panelRef}
      selectedLabel={elementLabel(selected)}
      canvasOverlay={
        <>
          <button
            type="button"
            className="n8n-fab n8n-fab--bottom"
            onClick={() => {
              setOpen(true);
              setQuery('');
              setCursor(0);
            }}
          >
            +
          </button>
          <div className="n8n-hint">⌘K / Ctrl+K to add a node</div>
          {open && (
            <div className="n8n-palette-backdrop" onClick={() => setOpen(false)}>
              <div className="n8n-palette" onClick={(e) => e.stopPropagation()}>
                <input
                  autoFocus
                  className="n8n-search-input"
                  placeholder="Search for a node type…"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setCursor(0);
                  }}
                  onKeyDown={onPaletteKeyDown}
                />
                <div className="n8n-palette-list">
                  {filtered.map((entry, i) => (
                    <div
                      key={entry.type}
                      className={
                        i === cursor
                          ? 'n8n-node-item n8n-node-item--active'
                          : 'n8n-node-item'
                      }
                      onMouseEnter={() => setCursor(i)}
                      onClick={() => choose(entry.type)}
                    >
                      {entry.label}
                      <span className="n8n-node-item-hint">{entry.category}</span>
                    </div>
                  ))}
                  {filtered.length === 0 && (
                    <div className="n8n-node-item n8n-node-item--empty">No matches</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      }
    />
  );
}
