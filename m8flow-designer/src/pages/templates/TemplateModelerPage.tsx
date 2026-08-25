import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, FolderArchive } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import {
  exportTemplate,
  fetchTemplate,
  fetchTemplateFileContent,
  saveTemplateFileContent,
  type Template,
  type TemplateFile,
} from '@/lib/templatesApi';
import { ApiError, fetchConnectorsGrouped } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DiagramCanvas } from '@/pages/process-model-modeler/components/DiagramCanvas';
import type { DiagramCanvasHandle } from '@/pages/process-model-modeler/components/DiagramCanvasHandle';
import type { BpmnCanvasServiceTaskOperator } from '@/pages/process-model-modeler/components/BpmnCanvas';
import { SaveButton } from '@/pages/process-model-modeler/components/SaveButton';
import { SavedStatusPill } from '@/pages/process-model-modeler/components/SavedStatusPill';
import { downloadBlob, downloadTextFile } from '@/lib/download';

/** Same posture as ProcessModelModelerPage's own SavePhase — see that
 * file's doc comment for the full state-machine rationale (reused here,
 * not re-derived: 'dirty' shows the Save button, everything else shows
 * the pill; 'error' is a brief flash back to 'dirty'). */
type SavePhase = 'saved' | 'dirty' | 'saving' | 'error';

const ERROR_FLASH_MS = 2500;

function contentTypeForFile(fileType: TemplateFile['fileType']): string {
  switch (fileType) {
    case 'bpmn':
    case 'dmn':
      return 'application/xml';
    case 'json':
      return 'application/json';
    case 'md':
      return 'text/markdown';
    default:
      return 'application/octet-stream';
  }
}

/** First BPMN file if one exists, else the first DMN file — same
 * "editable diagram" precedence DiagramCanvas's own extension-based
 * dispatch expects. A template with neither (json/md only) has nothing
 * for this page to open — surfaced as an explicit error, not a silent
 * blank canvas. */
function pickPrimaryFile(files: TemplateFile[]): TemplateFile | null {
  return files.find((f) => f.fileType === 'bpmn') ?? files.find((f) => f.fileType === 'dmn') ?? null;
}

/**
 * Template modeler — bpmn-js/dmn-js editor for one template's primary
 * diagram file (Template modeler map, ticket 03 —
 * `.scratch/template-modeler/`). Reuses the Process Modeler's own
 * `DiagramCanvas`/header/save-pill chrome rather than a parallel
 * implementation — same posture the Process Modeler map itself used for
 * BPMN vs. DMN ("one canvas, dispatch by extension").
 *
 * Draft-versioning (per `templatesApi.ts`'s own doc comment on
 * `saveTemplateFileContent`): saving a *published* template creates/reuses
 * a draft version with a **different** `id`. Handled here by re-anchoring
 * on the response and navigating to the new id — which, since `xml` is
 * re-fetched on `templateId` change, causes one extra reload of the
 * just-saved content (selection/undo-stack reset, content unchanged).
 * Accepted as a known rough edge for this rare case (editing an
 * already-published template), not fixed further — no mockup or user ask
 * to preserve canvas state across a version fork.
 */
export default function TemplateModelerPage() {
  const { templateId: templateIdParam } = useParams<{ templateId: string }>();
  const navigate = useNavigate();
  const canvasRef = useRef<DiagramCanvasHandle>(null);

  const parsedId = templateIdParam ? Number(templateIdParam) : NaN;
  const validId = Number.isFinite(parsedId);

  const [template, setTemplate] = useState<Template | null>(null);
  const [primaryFile, setPrimaryFile] = useState<TemplateFile | null>(null);
  const [xml, setXml] = useState<string | null>(null);
  const [loading, setLoading] = useState(validId);
  const [notFound, setNotFound] = useState(!validId);
  const [error, setError] = useState<string | null>(null);
  const [savePhase, setSavePhase] = useState<SavePhase>('saved');

  // Draft-versioning can change the effective template id after a save
  // (see doc comment above) — kept in a ref so onReadFile/onWriteFile
  // below always target the *current* id without needing to be recreated
  // (and re-wired into an already-mounted BpmnCanvas) every time it changes.
  const currentIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!validId) {
      setTemplate(null);
      setPrimaryFile(null);
      setXml(null);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setError(null);

    fetchTemplate(parsedId, { includeContents: false })
      .then(async (tpl) => {
        if (cancelled) return;
        currentIdRef.current = tpl.id;
        const primary = pickPrimaryFile(tpl.files);
        if (!primary) {
          setTemplate(tpl);
          setPrimaryFile(null);
          setXml(null);
          setError('This template has no BPMN or DMN file to open in the modeler.');
          return;
        }
        const content = await fetchTemplateFileContent(tpl.id, primary.fileName);
        if (cancelled) return;
        setTemplate(tpl);
        setPrimaryFile(primary);
        setXml(content);
        setSavePhase('saved');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setTemplate(null);
        setPrimaryFile(null);
        setXml(null);
        // fetchTemplate/fetchTemplateFileContent both throw ApiError with a
        // real HTTP status — 404 reads as "not found", everything else as
        // a visible error (same convention as ProcessModelModelerPage).
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load template');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [parsedId, validId]);

  const handleDirtyChange = useCallback((dirty: boolean) => {
    setSavePhase((phase) => {
      if (phase === 'saving' || phase === 'error') return phase;
      return dirty ? 'dirty' : 'saved';
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (!canvasRef.current || !primaryFile || currentIdRef.current == null) return;
    setSavePhase('saving');
    try {
      const currentXml = await canvasRef.current.saveXML();
      const updated = await saveTemplateFileContent(
        currentIdRef.current,
        primaryFile.fileName,
        currentXml,
        contentTypeForFile(primaryFile.fileType),
      );
      canvasRef.current.markSaved();
      setSavePhase('saved');
      setTemplate(updated);
      if (updated.id !== currentIdRef.current) {
        // Draft-versioning fork — re-anchor the route on the real id (see
        // this file's own doc comment for the resulting reload tradeoff).
        currentIdRef.current = updated.id;
        navigate(`/templates/${updated.id}`, { replace: true });
      }
    } catch {
      setSavePhase('error');
      setTimeout(() => setSavePhase('dirty'), ERROR_FLASH_MS);
    }
  }, [primaryFile, navigate]);

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
    if (!canvasRef.current || !primaryFile) return;
    const savedXml = await canvasRef.current.saveXML();
    downloadTextFile(primaryFile.fileName, savedXml, contentTypeForFile(primaryFile.fileType));
  }

  /** Distinct from Download above: this downloads *every* file in the
   * template (a zip, via the same export endpoint the gallery's per-card
   * action uses), not just the primary diagram's current in-editor XML. */
  async function handleExport() {
    if (currentIdRef.current == null || !template) return;
    const blob = await exportTemplate(currentIdRef.current);
    downloadBlob(`${template.templateKey}-v${template.version}.zip`, blob);
  }

  // JSON Schema "Launch Editor" round trip, same mechanism
  // ProcessModelModelerPage wires for process models — reads/writes an
  // arbitrary *other* file in this same template. Non-primary file
  // viewer/editor routes (dmn/md) are out of this ticket's scope (see
  // map's "Not yet specified"); this only answers BpmnCanvas's own
  // in-place read/write round trip, not full page navigation to them.
  const handleReadFile = useCallback(
    (name: string) => fetchTemplateFileContent(currentIdRef.current ?? parsedId, name),
    [parsedId],
  );
  const handleWriteFile = useCallback(async (name: string, content: string) => {
    if (currentIdRef.current == null) return;
    await saveTemplateFileContent(currentIdRef.current, name, content);
  }, []);

  const handleFetchServiceTaskOperators = useCallback(async (): Promise<BpmnCanvasServiceTaskOperator[]> => {
    const groups = await fetchConnectorsGrouped();
    return groups.flatMap((group) =>
      group.operations.map((operation) => ({ id: operation.id, parameters: operation.parameters })),
    );
  }, []);

  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <header className="flex flex-none items-center justify-between gap-3 border-b border-border px-6 py-3">
        <nav
          aria-label="Breadcrumb"
          className="flex min-w-0 items-center gap-1.5 overflow-hidden text-[13.5px] text-muted-foreground"
        >
          <Link to="/templates" className="shrink-0 text-info no-underline hover:underline">
            Templates
          </Link>
          <span aria-hidden="true">/</span>
          <span className="min-w-0 truncate font-mono font-semibold text-foreground" aria-current="page">
            {template?.name ?? primaryFile?.fileName ?? templateIdParam}
          </span>
          {template ? (
            <Badge variant={template.isPublished ? 'success' : 'outline'} className="shrink-0">
              {template.isPublished ? 'Published' : 'Draft'} · v{template.version}
            </Badge>
          ) : null}
        </nav>
        <div className="flex flex-none items-center gap-2.5">
          {savePhase === 'dirty' ? (
            <SaveButton onClick={() => void handleSave()} />
          ) : (
            <SavedStatusPill status={savePhase === 'saving' ? 'saving' : savePhase === 'error' ? 'error' : 'saved'} />
          )}
          <Button
            type="button"
            variant="pill-outline"
            size="pill"
            onClick={() => void handleExport()}
            disabled={!template}
            className="gap-1.5"
          >
            <FolderArchive className="size-3.5" strokeWidth={2.2} />
            Export
          </Button>
          <Button
            type="button"
            variant="pill-info"
            size="pill"
            onClick={handleDownload}
            disabled={!xml || !primaryFile}
            className="gap-1.5"
          >
            <Download className="size-3.5" strokeWidth={2.2} />
            Download
          </Button>
        </div>
      </header>

      <main className="min-h-0 flex-1">
        {!validId || notFound ? (
          <p className="p-6 text-sm text-muted-foreground" role="status">
            Template not found.
          </p>
        ) : loading ? (
          <p className="p-6 text-sm text-muted-foreground" aria-busy="true">
            Loading template…
          </p>
        ) : error ? (
          <p className="p-6 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : xml != null && primaryFile ? (
          <DiagramCanvas
            ref={canvasRef}
            fileName={primaryFile.fileName}
            xml={xml}
            onDirtyChange={handleDirtyChange}
            files={template?.files.map((f) => ({ name: f.fileName })) ?? []}
            onReadFile={handleReadFile}
            onWriteFile={handleWriteFile}
            onFetchServiceTaskOperators={handleFetchServiceTaskOperators}
          />
        ) : null}
      </main>
    </div>
  );
}
