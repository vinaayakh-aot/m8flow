import { lazy, Suspense, useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { Link, useOutletContext, useParams } from 'react-router-dom';

import { ApiError } from '@/lib/api';
import { fetchProcessInstanceDetail, type ProcessInstanceDetail } from '@/lib/processInstancesApi';
import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { downloadTextFile } from '@/lib/download';
import { formatDuration } from '@/pages/process-model-detail/components/ProcessModelOverview';
import { formatRelativeTime } from '@/lib/relativeTime';

// Lazy, same reasoning as the Process Modeler's own routes (App.tsx):
// bpmn-js's raw ESM doesn't resolve under Vitest's Node-based SSR module
// runner, and it keeps the ~2MB dependency out of every other route's chunk.
const InstanceDiagramViewer = lazy(() =>
  import('./components/InstanceDiagramViewer').then((m) => ({ default: m.InstanceDiagramViewer })),
);

/**
 * Process Instance detail — metadata + a read-only BPMN diagram colored
 * by live task state (Process Instances + task-state map, ticket 03).
 * Fetches GET /v1.0/m8flow/process-instances/{id} (ticket 01's backend).
 */
export default function ProcessInstanceDetailPage() {
  const { instanceId: instanceIdParam } = useParams<{ instanceId: string }>();
  const { scopedTenantId, isSuperAdmin } = useOutletContext<AppShellOutletContext>();
  const needsTenant = isSuperAdmin && !scopedTenantId;

  const parsedId = instanceIdParam ? Number(instanceIdParam) : NaN;
  const validId = Number.isFinite(parsedId);

  const [detail, setDetail] = useState<ProcessInstanceDetail | null>(null);
  const [loading, setLoading] = useState(!needsTenant && validId);
  const [notFound, setNotFound] = useState(!validId);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (needsTenant || !validId) {
      setDetail(null);
      setLoading(false);
      setNotFound(!needsTenant && !validId);
      setError(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setError(null);

    fetchProcessInstanceDetail(parsedId, scopedTenantId)
      .then((payload) => {
        if (!cancelled) setDetail(payload);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setDetail(null);
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load process instance');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [parsedId, validId, scopedTenantId, needsTenant]);

  function handleDownload() {
    if (!detail?.bpmn_xml) return;
    downloadTextFile(`${detail.process_model_identifier.replace('/', '-')}.bpmn`, detail.bpmn_xml);
  }

  return (
    <div className="flex min-h-screen flex-1 flex-col">
      <header className="flex flex-none items-center justify-between gap-3 border-b border-border px-6 py-3">
        <nav
          aria-label="Breadcrumb"
          className="flex min-w-0 items-center gap-1.5 overflow-hidden text-[13.5px] text-muted-foreground"
        >
          <Link to="/process-instances" className="shrink-0 text-info no-underline hover:underline">
            Process Instances
          </Link>
          <span aria-hidden="true">/</span>
          <span className="min-w-0 truncate font-mono font-semibold text-foreground" aria-current="page">
            {detail?.process_model_display_name ?? instanceIdParam} #{instanceIdParam}
          </span>
          {detail ? <StatusBadge status={detail.status} /> : null}
        </nav>
        <div className="flex flex-none items-center gap-2.5">
          <Button
            type="button"
            variant="pill-info"
            size="pill"
            onClick={handleDownload}
            disabled={!detail?.bpmn_xml}
            className="gap-1.5"
          >
            <Download className="size-3.5" strokeWidth={2.2} />
            Download
          </Button>
        </div>
      </header>

      {detail ? (
        <div className="flex flex-none flex-wrap items-center gap-x-6 gap-y-1 border-b border-border px-6 py-2.5 text-[13px] text-muted-foreground">
          <span>
            Started by <span className="font-medium text-foreground">{detail.started_by || '—'}</span>
          </span>
          <span>Started {formatRelativeTime(detail.start_in_seconds)}</span>
          <span>
            Duration{' '}
            {detail.start_in_seconds != null && detail.end_in_seconds != null
              ? formatDuration(detail.end_in_seconds - detail.start_in_seconds)
              : '—'}
          </span>
          <span>{detail.tasks.length} tracked tasks</span>
        </div>
      ) : null}

      <main className="min-h-0 flex-1">
        {needsTenant ? (
          <p className="p-6 text-sm text-muted-foreground">
            Process instances are tenant-scoped. Select a concrete tenant in the sidebar.
          </p>
        ) : loading ? (
          <p className="p-6 text-sm text-muted-foreground" aria-busy="true">
            Loading process instance…
          </p>
        ) : notFound ? (
          <p className="p-6 text-sm text-muted-foreground" role="status">
            Process instance not found.
          </p>
        ) : error ? (
          <p className="p-6 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : detail?.bpmn_xml ? (
          <Suspense fallback={<p className="p-6 text-sm text-muted-foreground">Loading diagram…</p>}>
            <InstanceDiagramViewer xml={detail.bpmn_xml} tasks={detail.tasks} />
          </Suspense>
        ) : detail ? (
          <p className="p-6 text-sm text-muted-foreground" role="status">
            No BPMN diagram is available for this instance (its process definition may have been removed).
          </p>
        ) : null}
      </main>
    </div>
  );
}
