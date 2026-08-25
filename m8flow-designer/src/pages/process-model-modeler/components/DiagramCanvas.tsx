import { forwardRef, lazy, Suspense } from 'react';

import type { BpmnCanvasFile, BpmnCanvasServiceTaskOperator } from './BpmnCanvas';
import type { CallActivitySearchProcessModel } from './CallActivitySearchDialog';
import type { DiagramCanvasHandle } from './DiagramCanvasHandle';

// Lazy, not static, imports: BpmnCanvas.tsx and DmnCanvas.tsx pull in
// bpmn-js and dmn-js respectively — two large, independent library trees
// that were previously *both* eagerly bundled and loaded together
// regardless of which file type was actually open (confirmed live: opening
// a .bpmn file still fetched dmn-js's own Modeler chunk). That's not just
// dead weight — dmn-js bundles its own copy of Inferno, and having it
// loaded alongside bpmn-js-properties-panel's Preact-based rendering on
// the same page is what caused a real, reproducible bug: clicking a
// properties-panel section header to expand it crashed with `Cannot add
// property __, object is not extensible` (two virtual-DOM libraries'
// internal DOM-node markers colliding) — confirmed fixed by no longer
// loading the other library's chunk for the file type not in use.
const BpmnCanvas = lazy(() =>
  import('./BpmnCanvas').then((module) => ({ default: module.BpmnCanvas })),
);
const DmnCanvas = lazy(() => import('./DmnCanvas').then((module) => ({ default: module.DmnCanvas })));

export type DiagramCanvasProps = {
  fileName: string;
  xml: string;
  onDirtyChange?: (dirty: boolean) => void;
  /** BPMN-only (DmnCanvas doesn't use these yet) — see BpmnCanvasProps. */
  files?: BpmnCanvasFile[];
  onReadFile?: (fileName: string) => Promise<string>;
  onWriteFile?: (fileName: string, content: string) => Promise<void>;
  onLaunchDmnEditor?: (fileName: string) => void;
  processModels?: CallActivitySearchProcessModel[];
  onLaunchCallActivityEditor?: (processModelId: string) => void;
  onFetchServiceTaskOperators?: () => Promise<BpmnCanvasServiceTaskOperator[]>;
};

/** Dispatches to the BPMN or DMN canvas by file extension. */
export const DiagramCanvas = forwardRef<DiagramCanvasHandle, DiagramCanvasProps>(
  function DiagramCanvas(
    {
      fileName,
      xml,
      onDirtyChange,
      files,
      onReadFile,
      onWriteFile,
      onLaunchDmnEditor,
      processModels,
      onLaunchCallActivityEditor,
      onFetchServiceTaskOperators,
    },
    ref,
  ) {
    const isDmn = fileName.toLowerCase().endsWith('.dmn');
    return (
      <Suspense fallback={null}>
        {isDmn ? (
          <DmnCanvas ref={ref} xml={xml} onDirtyChange={onDirtyChange} />
        ) : (
          <BpmnCanvas
            ref={ref}
            xml={xml}
            onDirtyChange={onDirtyChange}
            files={files}
            onReadFile={onReadFile}
            onWriteFile={onWriteFile}
            onLaunchDmnEditor={onLaunchDmnEditor}
            processModels={processModels}
            onLaunchCallActivityEditor={onLaunchCallActivityEditor}
            onFetchServiceTaskOperators={onFetchServiceTaskOperators}
          />
        )}
      </Suspense>
    );
  },
);
