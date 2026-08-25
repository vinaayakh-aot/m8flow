// PROTOTYPE — throwaway. Bootstraps BpmnModeler with all three real packages
// (bpmn-js, bpmn-js-properties-panel, bpmn-js-spiffworkflow) plus our custom
// n8n-style renderer, exactly the way m8flow-frontend's own
// `useDiagramModeler.ts` does it — see that file for the production wiring
// this prototype deliberately keeps minimal.
import { useEffect, useRef, useState } from 'react';
import BpmnModeler from 'bpmn-js/lib/Modeler';
import {
  BpmnPropertiesPanelModule,
  BpmnPropertiesProviderModule,
  // @ts-expect-error no upstream type declarations
} from 'bpmn-js-properties-panel';
// @ts-expect-error no upstream type declarations
import spiffworkflow from 'bpmn-js-spiffworkflow/app/spiffworkflow';
// @ts-expect-error no upstream type declarations
import spiffModdleExtension from 'bpmn-js-spiffworkflow/app/spiffworkflow/moddle/spiffworkflow.json';
import { n8nRendererModule } from './n8nRenderer';
import { SAMPLE_BPMN_XML } from './sampleProcess';

export function useN8nModeler() {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [modeler, setModeler] = useState<any>(null);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    if (!canvasRef.current || !panelRef.current) return undefined;

    const instance = new (BpmnModeler as any)({
      container: canvasRef.current,
      keyboard: { bindTo: document },
      propertiesPanel: { parent: panelRef.current },
      additionalModules: [
        spiffworkflow,
        BpmnPropertiesPanelModule,
        BpmnPropertiesProviderModule,
        n8nRendererModule,
      ],
      moddleExtensions: { spiffworkflow: spiffModdleExtension },
    });

    instance.importXML(SAMPLE_BPMN_XML).then(() => {
      instance.get('canvas').zoom('fit-viewport');
    });

    instance.on('selection.changed', (event: any) => {
      setSelected(event.newSelection[0] ?? null);
    });

    setModeler(instance);

    return () => {
      instance.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { canvasRef, panelRef, modeler, selected };
}
