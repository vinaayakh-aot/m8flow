import { useCallback, useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';

import {
  ApiError,
  createProcessModelFile,
  fetchConnectorsGrouped,
  fetchProcessModelDetail,
  fetchProcessModelFileContent,
  fetchProcessModels,
  saveProcessModelFileContent,
  type ProcessModelDetailFile,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { DiagramCanvas } from './components/DiagramCanvas';
import type { DiagramCanvasHandle } from './components/DiagramCanvasHandle';
import type { BpmnCanvasServiceTaskOperator } from './components/BpmnCanvas';
import type { CallActivitySearchProcessModel } from './components/CallActivitySearchDialog';
import { SaveButton } from './components/SaveButton';
import { SavedStatusPill } from './components/SavedStatusPill';
import { downloadTextFile } from '@/lib/download';
import { encodeProcessModelId } from '@/lib/processModelId';
import type { AppShellOutletContext } from '@/components/layout/AppShell';

/** Save/dirty state machine (decided on the manual-save ticket, HITL): the
 * Save button and the SavedStatusPill are never shown together — 'dirty'
 * shows the button, everything else shows the pill. 'error' is a brief
 * flash before automatically reverting to 'dirty' (the save didn't
 * actually succeed, so the diagram is still unsaved) rather than a
 * persistent state. */
type SavePhase = 'saved' | 'dirty' | 'saving' | 'error';

const ERROR_FLASH_MS = 2500;

/**
 * Process Modeler — BPMN/DMN editor for one file inside a process model.
 * Fetches GET /v1.0/m8flow/process-models/{id}/files/{fileName} and mounts a
 * real, editable canvas (bpmn-js + bpmn-js-spiffworkflow, or dmn-js).
 * Manual save (Cmd/Ctrl+S or the Save button) PUTs the current XML back;
 * the RBAC gap logged on the backend-endpoints ticket (a .bpmn save needs
 * m8flow-bpmn-core's V1 "admin" role, not just the editor group) is
 * deliberately not special-cased here — it surfaces as the same generic
 * "Save failed" flash as any other error (decided, not an oversight).
 */
export default function ProcessModelModelerPage() {
  const { processModelId, fileName } = useParams<{
    processModelId: string;
    fileName: string;
  }>();
  const navigate = useNavigate();
  const { scopedTenantId, isSuperAdmin } = useOutletContext<AppShellOutletContext>();
  const needsTenant = isSuperAdmin && !scopedTenantId;
  const modifiedId = processModelId ?? '';
  const file = fileName ?? '';
  const canvasRef = useRef<DiagramCanvasHandle>(null);

  const [xml, setXml] = useState<string | null>(null);
  const [loading, setLoading] = useState(!needsTenant && Boolean(modifiedId) && Boolean(file));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savePhase, setSavePhase] = useState<SavePhase>('saved');
  // Breadcrumb group label (header-chrome ticket, HITL): `fetchProcessModelDetail`
  // is the same detail call ProcessModelOverview already uses — reused here
  // rather than `fetchProcessGroups`'s list-and-find, since the model's own
  // detail response already carries its group's id/display name directly.
  // Falls back to the raw group id (the first `:`-segment of `modifiedId`)
  // until the fetch resolves, or forever if it fails — a label-only lookup
  // isn't worth a visible error state.
  const [groupInfo, setGroupInfo] = useState<{ id: string; displayName: string } | null>(null);
  // This model's own files (Task Configuration Parity plan, Phase 1) — feeds
  // BpmnCanvas's JSON Schema Filename dropdown. Same fetch as groupInfo above
  // (ProcessModelDetailResponse carries both), so no extra request.
  const [modelFiles, setModelFiles] = useState<ProcessModelDetailFile[]>([]);
  // Every process model in this tenant (Task Configuration Parity plan,
  // Phase 3) — feeds Call Activity's "Search" picker. Cross-model, so a
  // separate fetch from modelFiles above (which is scoped to *this* model).
  const [processModels, setProcessModels] = useState<CallActivitySearchProcessModel[]>([]);

  useEffect(() => {
    if (needsTenant || !modifiedId || !file) {
      setXml(null);
      setLoading(false);
      setNotFound(!needsTenant && (!modifiedId || !file));
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setError(null);

    fetchProcessModelFileContent(modifiedId, file, scopedTenantId)
      .then((content) => {
        if (!cancelled) {
          setXml(content);
          setSavePhase('saved');
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setXml(null);
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
          setError(null);
          return;
        }
        setNotFound(false);
        setError(err instanceof Error ? err.message : 'Failed to load file');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [modifiedId, file, scopedTenantId, needsTenant]);

  useEffect(() => {
    if (needsTenant || !modifiedId) {
      setGroupInfo(null);
      setModelFiles([]);
      return undefined;
    }

    let cancelled = false;
    fetchProcessModelDetail(modifiedId, scopedTenantId)
      .then((detail) => {
        if (!cancelled) {
          setGroupInfo({ id: detail.group_id, displayName: detail.group_display_name });
          setModelFiles(detail.files);
        }
      })
      .catch(() => {
        // Breadcrumb degrades to the raw group id below, and the JSON Schema
        // dropdown degrades to empty — neither is worth a visible error for
        // what's otherwise a background enrichment fetch.
      });

    return () => {
      cancelled = true;
    };
  }, [modifiedId, scopedTenantId, needsTenant]);

  useEffect(() => {
    if (needsTenant) {
      setProcessModels([]);
      return undefined;
    }

    let cancelled = false;
    fetchProcessModels(scopedTenantId)
      .then((models) => {
        if (!cancelled) {
          setProcessModels(
            // fetchProcessModels' own `id` is `/`-separated (the raw API/disk
            // form, per lib/processModelId.ts's own doc comment) — encode to
            // `:` before handing it to the search dialog, since it becomes
            // both the bpmn:calledElement value (typed into "Process ID") and
            // the argument handleLaunchCallActivityEditor below passes to
            // fetchProcessModelDetail, which expects the `:` route form.
            models.map((m) => ({
              id: encodeProcessModelId(m.id),
              displayName: m.display_name,
              groupDisplayName: m.group_display_name,
            })),
          );
        }
      })
      .catch(() => {
        // Search picker degrades to an empty result list — not worth a
        // visible error for what's otherwise a background enrichment fetch.
      });

    return () => {
      cancelled = true;
    };
  }, [scopedTenantId, needsTenant]);

  // Call Activity's "Launch Editor" (Task Configuration Parity plan, Phase
  // 3) — resolves the called process model's *primary* file (same lookup
  // ProcessModelOverview.tsx already uses for its own "Open in modeler"
  // link) and navigates there.
  const handleLaunchCallActivityEditor = useCallback(
    async (calledProcessModelId: string) => {
      try {
        const detail = await fetchProcessModelDetail(calledProcessModelId, scopedTenantId);
        const primaryFile = detail.files.find((f) => f.primary);
        if (!primaryFile) return;
        navigate(`/processes/${encodeProcessModelId(detail.id)}/modeler/${encodeURIComponent(primaryFile.name)}`);
      } catch (err) {
        console.error('Failed to open called process model:', err);
      }
    },
    [navigate, scopedTenantId],
  );

  // Service Task's connector operator dropdown (Task Configuration Parity
  // plan, Phase 4). Spike outcome: m8flow-frontend's own `/service-tasks`
  // call has no matching backend route; `GET /connectors-grouped` is the
  // real, working source (same one the Connectors page itself uses) —
  // flattened here from "grouped by connector" into the flat
  // `{id, parameters}[]` shape bpmn-js-spiffworkflow's
  // ServiceTaskOperatorSelect expects.
  const handleFetchServiceTaskOperators = useCallback(async (): Promise<BpmnCanvasServiceTaskOperator[]> => {
    const groups = await fetchConnectorsGrouped();
    return groups.flatMap((group) =>
      group.operations.map((operation) => ({
        id: operation.id,
        parameters: operation.parameters,
      })),
    );
  }, []);

  // JSON Schema "Launch Editor" (User Task Web Form). Create Files writes
  // *-schema.json / *-uischema.json / *-exampledata.json via POST; later
  // edits PUT the same files. After create, the listenEvent binds the
  // schema filename onto the selected task.
  const handleReadModelFile = useCallback(
    (name: string) => fetchProcessModelFileContent(modifiedId, name, scopedTenantId),
    [modifiedId, scopedTenantId],
  );
  const handleWriteModelFile = useCallback(
    async (name: string, content: string) => {
      await saveProcessModelFileContent(modifiedId, name, content, scopedTenantId);
    },
    [modifiedId, scopedTenantId],
  );
  const handleCreateModelFile = useCallback(
    async (name: string, content: string) => {
      await createProcessModelFile(modifiedId, { file_name: name, content }, scopedTenantId);
    },
    [modifiedId, scopedTenantId],
  );
  const handleFormFilesChanged = useCallback(() => {
    void fetchProcessModelDetail(modifiedId, scopedTenantId)
      .then((detail) => {
        setGroupInfo({ id: detail.group_id, displayName: detail.group_display_name });
        setModelFiles(detail.files);
      })
      .catch(() => {
        // Dropdown refresh is best-effort — the new filename is already
        // written onto the task via the Launch Editor listenEvent.
      });
  }, [modifiedId, scopedTenantId]);

  // Business Rule Task's "Launch Editor" (Task Configuration Parity plan,
  // Phase 2) — navigates to the chosen .dmn file's own modeler page, reusing
  // this same route (DiagramCanvas dispatches to DmnCanvas by extension).
  // m8flow-frontend's own onLaunchDmnEditor is a no-op today (its one real
  // consumer, TemplateFileDiagramPage, never wires anything real here) —
  // this is a genuine improvement, not a straight port.
  const handleLaunchDmnEditor = useCallback(
    (name: string) => {
      navigate(`/processes/${modifiedId}/modeler/${encodeURIComponent(name)}`);
    },
    [navigate, modifiedId],
  );

  const handleDirtyChange = useCallback((dirty: boolean) => {
    // Only 'saved' <-> 'dirty' react to canvas edits/undo; 'saving' and the
    // brief 'error' flash own the pill until they resolve on their own.
    setSavePhase((phase) => {
      if (phase === 'saving' || phase === 'error') return phase;
      return dirty ? 'dirty' : 'saved';
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (!canvasRef.current) return;
    setSavePhase('saving');
    try {
      const currentXml = await canvasRef.current.saveXML();
      await saveProcessModelFileContent(modifiedId, file, currentXml, scopedTenantId);
      canvasRef.current.markSaved();
      setSavePhase('saved');
    } catch {
      setSavePhase('error');
      setTimeout(() => setSavePhase('dirty'), ERROR_FLASH_MS);
    }
  }, [modifiedId, file, scopedTenantId]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (savePhase === 'dirty') {
          void handleSave();
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [savePhase, handleSave]);

  async function handleDownload() {
    if (!canvasRef.current) return;
    const savedXml = await canvasRef.current.saveXML();
    downloadTextFile(file || 'diagram.bpmn', savedXml);
  }

  // Mockup fidelity decision (HITL, header-chrome ticket): the mockup's
  // three-crumb breadcrumb (Process Groups / Group / file) has no crumb at
  // all for "this model's own detail page" — the group crumb, linking to
  // the group-filtered process list, is the closest equivalent. This trades
  // one click for two to get back to the model detail page (Group list →
  // find the model → open it) versus the old single "← group:model" link
  // straight there. A deliberate fidelity tradeoff, not an oversight.
  const groupId = groupInfo?.id ?? modifiedId.split(':')[0] ?? '';
  const groupLabel = groupInfo?.displayName || groupId || 'Process group';

  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <header className="flex flex-none items-center justify-between gap-3 border-b border-border px-6 py-3">
        <nav
          aria-label="Breadcrumb"
          className="flex min-w-0 items-center gap-1.5 overflow-hidden text-[13.5px] text-muted-foreground"
        >
          <Link to="/processes" className="shrink-0 text-info no-underline hover:underline">
            Process Groups
          </Link>
          <span aria-hidden="true">/</span>
          <Link
            to={groupId ? `/processes?group=${encodeURIComponent(groupId)}` : '/processes'}
            className="min-w-0 truncate text-info no-underline hover:underline"
          >
            {groupLabel}
          </Link>
          <span aria-hidden="true">/</span>
          <span className="truncate font-mono font-semibold text-foreground" aria-current="page">
            {file}
          </span>
        </nav>
        <div className="flex flex-none items-center gap-2.5">
          {savePhase === 'dirty' ? (
            <SaveButton onClick={() => void handleSave()} />
          ) : (
            <SavedStatusPill status={savePhase === 'saving' ? 'saving' : savePhase === 'error' ? 'error' : 'saved'} />
          )}
          <Button
            type="button"
            variant="pill-info"
            size="pill"
            onClick={handleDownload}
            disabled={!xml}
            className="gap-1.5"
          >
            <Download className="size-3.5" strokeWidth={2.2} />
            Download
          </Button>
        </div>
      </header>

      <main className="min-h-0 flex-1">
        {needsTenant ? (
          <p className="p-6 text-sm text-muted-foreground">
            Process models are tenant-scoped. Select a concrete tenant in the sidebar.
          </p>
        ) : loading ? (
          <p className="p-6 text-sm text-muted-foreground" aria-busy="true">
            Loading file…
          </p>
        ) : notFound ? (
          <p className="p-6 text-sm text-muted-foreground" role="status">
            File not found.
          </p>
        ) : error ? (
          <p className="p-6 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : xml != null ? (
          <DiagramCanvas
            ref={canvasRef}
            fileName={file}
            xml={xml}
            onDirtyChange={handleDirtyChange}
            files={modelFiles}
            onReadFile={handleReadModelFile}
            onWriteFile={handleWriteModelFile}
            onCreateFile={handleCreateModelFile}
            onFilesChanged={handleFormFilesChanged}
            onLaunchDmnEditor={handleLaunchDmnEditor}
            processModels={processModels}
            onLaunchCallActivityEditor={handleLaunchCallActivityEditor}
            onFetchServiceTaskOperators={handleFetchServiceTaskOperators}
          />
        ) : null}
      </main>
    </div>
  );
}
