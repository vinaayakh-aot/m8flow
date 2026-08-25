// PROTOTYPE — throwaway. Deliberately bypasses App.tsx / m8flowAppRoutes.tsx
// (no router, no Keycloak/tenant gating) so this stays a read-only design
// prototype against a static sample process, not a change to the real app
// shell. See prototype-n8n-bpmn.html and README.md.
import React from 'react';
import { createRoot } from 'react-dom/client';

// Stock bpmn-js / properties-panel / spiffworkflow CSS assets — same fixed
// package paths m8flow-frontend's own ReactDiagramEditor.tsx imports.
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css';
import 'bpmn-js/dist/assets/bpmn-js.css';
import '@bpmn-io/properties-panel/assets/properties-panel.css';
import 'bpmn-js-spiffworkflow/app/css/app.css';

import { PrototypeRoot } from './PrototypeRoot';

createRoot(document.getElementById('root') as HTMLElement).render(<PrototypeRoot />);
