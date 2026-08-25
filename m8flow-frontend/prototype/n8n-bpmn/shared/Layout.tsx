// PROTOTYPE — throwaway. The macro layout the user asked for directly (not
// something being varied across A/B/C): the designer canvas fills the whole
// viewport, the properties panel is fixed to the right quarter of the
// screen. Each variant only changes what floats on top of the canvas and how
// the panel's own content behaves.
import React from 'react';

type LayoutProps = {
  canvasRef: React.RefObject<HTMLDivElement>;
  panelRef: React.RefObject<HTMLDivElement>;
  canvasOverlay?: React.ReactNode;
  panelHeader?: React.ReactNode;
  selectedLabel?: string | null;
};

export function Layout({
  canvasRef,
  panelRef,
  canvasOverlay,
  panelHeader,
  selectedLabel,
}: LayoutProps) {
  return (
    <div className="n8n-shell">
      <div className="n8n-canvas-area">
        <div ref={canvasRef} className="n8n-canvas" />
        {canvasOverlay}
      </div>
      <div className="n8n-panel">
        <div className="n8n-panel-header">
          {panelHeader ?? (
            <>
              <span className="n8n-panel-title">
                {selectedLabel ?? 'Nothing selected'}
              </span>
              <span className="n8n-panel-subtitle">
                Click a node on the canvas to configure it
              </span>
            </>
          )}
        </div>
        <div ref={panelRef} className="n8n-panel-body" />
      </div>
    </div>
  );
}
