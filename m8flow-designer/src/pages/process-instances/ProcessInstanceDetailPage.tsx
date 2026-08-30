import { lazy, Suspense, type ReactNode, useEffect, useState } from 'react';
import { Link2, Pause, Play, Square } from 'lucide-react';
import { Link, useOutletContext, useParams } from 'react-router-dom';

import { ApiError } from '@/lib/api';
import {
  fetchProcessInstanceDetail,
  postProcessInstanceLifecycle,
  type ProcessInstanceDetail,
  type ProcessInstanceLifecycleAction,
} from '@/lib/processInstancesApi';
import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { processInstanceLifecycleVisibility } from './lifecycleActions';
import { ProcessInstanceCompletableTasksTable } from './components/ProcessInstanceCompletableTasksTable';
import { ProcessInstanceCompletedTasksTable } from './components/ProcessInstanceCompletedTasksTable';
import { ProcessInstanceEventsTable } from './components/ProcessInstanceEventsTable';
import { ProcessInstanceMilestonesTable } from './components/ProcessInstanceMilestonesTable';

const InstanceDiagramViewer = lazy(() =>
  import('./components/InstanceDiagramViewer').then((m) => ({ default: m.InstanceDiagramViewer })),
);

type DetailTab = 'diagram' | 'milestones' | 'events' | 'messages' | 'tasks';

const TABS: { id: DetailTab; label: string }[] = [
  { id: 'diagram', label: 'Diagram' },
  { id: 'milestones', label: 'Milestones' },
  { id: 'events', label: 'Events' },
  { id: 'messages', label: 'Messages' },
  { id: 'tasks', label: 'Tasks' },
];

function formatUtcTimestamp(epochSeconds: number | null | undefined): string {
  if (epochSeconds == null) {
    return '—';
  }
  const d = new Date(epochSeconds * 1000);
  if (Number.isNaN(d.getTime())) {
    return '—';
  }
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

function IconAction({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon-lg"
      className="rounded-full"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </Button>
  );
}

function MetaCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2.5 text-[13.5px]">
      <span className="w-[90px] shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/**
 * Process instance detail — mockup shell: breadcrumb, title + icon
 * actions, metadata grid, Tasks I can complete, tab bodies. Download is
 * gone. Copy link is the current URL. Updated / Last milestone come from
 * the designer GET; Revision stays `—` (no git, no hash, no GET key).
 */
export default function ProcessInstanceDetailPage() {
  const { instanceId: instanceIdParam } = useParams<{ instanceId: string }>();
  const { scopedTenantId, isSuperAdmin, canManageProcesses } = useOutletContext<AppShellOutletContext>();
  const needsTenant = isSuperAdmin && !scopedTenantId;
  const canLifecycle = Boolean(canManageProcesses);

  const parsedId = Number.isFinite(Number(instanceIdParam)) ? Number(instanceIdParam) : NaN;
  const validId = Number.isFinite(parsedId);

  const [detail, setDetail] = useState<ProcessInstanceDetail | null>(null);
  const [loading, setLoading] = useState(!needsTenant && validId);
  const [notFound, setNotFound] = useState(!validId);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [tab, setTab] = useState<DetailTab>('diagram');

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

  async function handleCopyLink() {
    try {
      await navigator.clipboard?.writeText(window.location.href);
    } catch {
      /* clipboard can reject in insecure contexts */
    }
  }

  async function handleLifecycle(action: ProcessInstanceLifecycleAction) {
    if (!validId || actionBusy) return;
    if (action === 'terminate' && !window.confirm('Terminate this process instance? This cannot be undone.')) {
      return;
    }
    setActionBusy(true);
    setError(null);
    try {
      await postProcessInstanceLifecycle(parsedId, action, scopedTenantId);
      const next = await fetchProcessInstanceDetail(parsedId, scopedTenantId);
      setDetail(next);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update process instance');
    } finally {
      setActionBusy(false);
    }
  }

  const actions = detail && canLifecycle ? processInstanceLifecycleVisibility(detail.status) : null;

  return (
    <div className="flex min-h-screen flex-1 flex-col px-11 py-7">
      <nav
        aria-label="Breadcrumb"
        className="mb-[18px] flex min-w-0 flex-wrap items-center gap-1.5 text-[13.5px] text-muted-foreground"
      >
        <Link to="/process-instances" className="shrink-0 font-semibold text-info no-underline hover:underline">
          Process Instances
        </Link>
        <span aria-hidden="true">/</span>
        <span className="min-w-0 truncate font-mono font-semibold text-foreground" aria-current="page">
          {detail?.process_model_display_name ?? instanceIdParam} #{instanceIdParam}
        </span>
      </nav>

      <div className="mb-5 flex flex-wrap items-center gap-4">
        <h1 className="m-0 font-display text-[clamp(24px,2.4vw,32px)] font-semibold tracking-tight text-foreground">
          Process Instance ID: {instanceIdParam}
        </h1>
        <div className="flex items-center gap-2">
          <IconAction label="Copy link" onClick={handleCopyLink}>
            <Link2 className="size-4 text-muted-foreground" strokeWidth={1.8} />
          </IconAction>
          {actions?.terminate ? (
            <IconAction
              label="Terminate"
              onClick={() => handleLifecycle('terminate')}
              disabled={actionBusy}
            >
              <Square className="size-3.5 fill-destructive text-destructive" strokeWidth={0} />
            </IconAction>
          ) : null}
          {actions?.suspend ? (
            <IconAction
              label="Suspend"
              onClick={() => handleLifecycle('suspend')}
              disabled={actionBusy}
            >
              <Pause className="size-3.5 fill-muted-foreground text-muted-foreground" strokeWidth={0} />
            </IconAction>
          ) : null}
          {actions?.resume ? (
            <IconAction
              label="Resume"
              onClick={() => handleLifecycle('resume')}
              disabled={actionBusy}
            >
              <Play className="size-3.5 fill-muted-foreground text-muted-foreground" strokeWidth={0} />
            </IconAction>
          ) : null}
        </div>
      </div>

      {needsTenant ? (
        <p className="text-sm text-muted-foreground">
          Process instances are tenant-scoped. Select a concrete tenant in the sidebar.
        </p>
      ) : loading ? (
        <p className="text-sm text-muted-foreground" aria-busy="true">
          Loading process instance…
        </p>
      ) : notFound ? (
        <p className="text-sm text-muted-foreground" role="status">
          Process instance not found.
        </p>
      ) : error && !detail ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : detail ? (
        <>
          {error ? (
            <p className="mb-4 text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          <Card variant="bordered" className="mb-[26px] grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-x-7 gap-y-3.5 px-[22px] py-[18px]">
            <MetaCell label="Status">
              <StatusBadge status={detail.status} />
            </MetaCell>
            <MetaCell label="Started by">{detail.started_by || '—'}</MetaCell>
            <MetaCell label="Started">
              <span className="font-mono text-[12.5px]">{formatUtcTimestamp(detail.start_in_seconds)}</span>
            </MetaCell>
            <MetaCell label="Updated">
              <span className="font-mono text-[12.5px]">{formatUtcTimestamp(detail.updated_at_in_seconds)}</span>
            </MetaCell>
            <MetaCell label="Last milestone">
              {detail.last_milestone_bpmn_name?.trim() || '—'}
            </MetaCell>
            <MetaCell label="Revision">
              <span className="font-mono text-xs text-muted-foreground">—</span>
            </MetaCell>
          </Card>

          <div className="mb-7">
            <ProcessInstanceCompletableTasksTable instanceId={parsedId} tenantId={scopedTenantId} />
          </div>

          <div className="mb-5 flex items-center gap-[26px] border-b border-border">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={tab === item.id}
                onClick={() => setTab(item.id)}
                className={cn(
                  'cursor-pointer border-x-0 border-t-0 border-b-2 bg-transparent py-2.5 font-sans text-[14.5px]',
                  tab === item.id
                    ? 'border-info font-semibold text-info'
                    : 'border-transparent font-medium text-muted-foreground',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === 'diagram' ? (
            detail.bpmn_xml ? (
              <Card variant="bordered" className="relative h-[520px] overflow-hidden">
                <Suspense fallback={<p className="p-6 text-sm text-muted-foreground">Loading diagram…</p>}>
                  <InstanceDiagramViewer xml={detail.bpmn_xml} tasks={detail.tasks} />
                </Suspense>
              </Card>
            ) : (
              <p className="text-sm text-muted-foreground" role="status">
                No BPMN diagram is available for this instance (its process definition may have been
                removed).
              </p>
            )
          ) : null}

          {tab === 'milestones' ? (
            <ProcessInstanceMilestonesTable instanceId={parsedId} tenantId={scopedTenantId} />
          ) : null}

          {tab === 'events' ? (
            <ProcessInstanceEventsTable instanceId={parsedId} tenantId={scopedTenantId} />
          ) : null}

          {tab === 'messages' ? (
            <Card variant="bordered">
              <p className="px-[22px] py-11 text-center text-[13.5px] text-muted-foreground">
                No messages recorded for this process instance.
              </p>
            </Card>
          ) : null}

          {tab === 'tasks' ? (
            <ProcessInstanceCompletedTasksTable instanceId={parsedId} tenantId={scopedTenantId} />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
