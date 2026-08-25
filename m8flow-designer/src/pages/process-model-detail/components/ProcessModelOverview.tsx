import { Download, Folder, MoreVertical, Pencil, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';

import { fetchProcessModelFileContent, type ProcessModelDetail, type ProcessModelDetailFile } from '@/lib/api';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { downloadTextFile } from '@/lib/download';
import { encodeProcessModelId } from '@/lib/processModelId';
import { formatRelativeTime } from '@/lib/relativeTime';
import { cn } from '@/lib/utils';

// This page's placeholder/"coming soon" actions (Start process, Open in
// modeler when no file exists yet, Save as template, Add file, More
// actions) render `disabled` but are meant to *look* fully live, matching
// the mockup — not dimmed the way Button's own `disabled:opacity-50`
// otherwise renders every other disabled Button in the app. This override
// is the one deliberate exception to that rule.
const inertBtn = 'cursor-default select-none disabled:cursor-default disabled:opacity-100';

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) {
    return '—';
  }
  const n = Math.max(0, Math.floor(seconds));
  if (n < 60) {
    return `${n}s`;
  }
  const minutes = Math.floor(n / 60);
  const rem = n % 60;
  return rem ? `${minutes}m ${rem}s` : `${minutes}m`;
}

export function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  return `${Math.round(size / 1024)} KB`;
}

export function fileKind(name: string): { ext: string; label: string } {
  const lower = name.toLowerCase();
  if (lower.endsWith('.bpmn')) {
    return { ext: 'BPMN', label: 'BPMN' };
  }
  if (lower.endsWith('.dmn')) {
    return { ext: 'DMN', label: 'DMN' };
  }
  if (lower.endsWith('.md')) {
    return { ext: 'MD', label: 'Markdown' };
  }
  if (lower.endsWith('.json')) {
    if (lower.includes('uischema')) {
      return { ext: 'JSON', label: 'UI schema' };
    }
    if (lower.includes('schema')) {
      return { ext: 'JSON', label: 'Form schema' };
    }
    return { ext: 'JSON', label: 'JSON' };
  }
  const dot = name.lastIndexOf('.');
  const ext = dot >= 0 ? name.slice(dot + 1).toUpperCase() : 'FILE';
  return { ext, label: ext };
}

function FileRow({
  file,
  modelId,
  tenantId,
}: {
  file: ProcessModelDetailFile;
  modelId: string;
  tenantId?: string | null;
}) {
  const kind = fileKind(file.name);
  const meta = `${kind.label} · ${formatBytes(file.size_bytes)} · updated ${formatRelativeTime(file.updated_at_in_seconds)}`;
  const iconTone = kind.ext === 'BPMN' ? 'bg-nav-active/15 text-info' : 'bg-muted text-muted-foreground';
  const modelerHref = `/processes/${encodeProcessModelId(modelId)}/modeler/${encodeURIComponent(file.name)}`;

  async function handleDownload() {
    const content = await fetchProcessModelFileContent(encodeProcessModelId(modelId), file.name, tenantId);
    downloadTextFile(file.name, content);
  }

  return (
    <div className="flex items-center gap-3.5 border-b border-border px-4 py-3.5 last:border-b-0">
      <div
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-lg font-mono text-[9.5px] font-bold',
          iconTone,
        )}
      >
        {kind.ext}
      </div>
      <div className="min-w-0 flex-1">
        <div className="break-words text-[13.5px] text-foreground">{file.name}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{meta}</div>
      </div>
      {file.primary ? (
        <span className="shrink-0 rounded-full bg-nav-active/15 px-2.5 py-0.5 text-[11.5px] font-semibold text-info">
          Primary
        </span>
      ) : null}
      <div className="flex shrink-0 items-center gap-1.5 text-muted-foreground">
        <Link
          to={modelerHref}
          title="Edit file"
          className="flex size-7 items-center justify-center rounded-md no-underline hover:bg-muted hover:text-info"
        >
          <Pencil className="size-4" strokeWidth={1.8} aria-hidden />
        </Link>
        <button
          type="button"
          title="Download file"
          onClick={() => void handleDownload()}
          className="flex size-7 items-center justify-center rounded-md hover:bg-muted hover:text-info"
        >
          <Download className="size-4" strokeWidth={1.8} aria-hidden />
        </button>
      </div>
    </div>
  );
}

export type ProcessModelOverviewProps = {
  detail: ProcessModelDetail;
  /** Needed for each file row's Download fetch — same tenant scope as the
   * detail fetch itself (super-admin's selected tenant, or null for
   * regular users whose tenant is cookie-scoped server-side). */
  tenantId?: string | null;
};

/**
 * Process-model overview layout matching Processes.dc.html inModel.
 * Live fields come from the detail API; mockup-only extras are omitted or
 * placeholder. Header/instance-start controls stay inert chrome; file
 * rows' Edit/Download are live (per-file-row entry-points ticket), and so
 * is the Recent instances table's own "View all"/per-row id (Process
 * Instances + task-state map, ticket 04 capstone).
 */
export function ProcessModelOverview({ detail, tenantId }: ProcessModelOverviewProps) {
  const groupHref = `/processes?group=${encodeURIComponent(detail.group_id)}`;
  const viewAllLabel = `View all ${detail.runs_30d}`;
  // "View all" pre-filters the shared Process Instances list to this
  // model's own display name — an approximate filter (substring match on
  // `search`, not a hard process-model-id constraint; see
  // ProcessInstancesPage's own doc comment), not a guarantee every result
  // belongs to this exact model. Accepted since the alternative was
  // teaching that page a dedicated process-model-id filter param for one
  // entry point.
  const viewAllHref = `/process-instances?search=${encodeURIComponent(detail.display_name)}`;
  const primaryFile = detail.files.find((f) => f.primary);
  const modelerHref = primaryFile
    ? `/processes/${encodeProcessModelId(detail.id)}/modeler/${encodeURIComponent(primaryFile.name)}`
    : null;

  return (
    <div data-testid="process-model-detail">
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Link
            to="/processes"
            className="mb-1.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-foreground no-underline"
          >
            ← All processes
          </Link>
          <h1 className="text-[32px] font-semibold tracking-tight break-words text-foreground">
            {detail.display_name}
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button type="button" disabled variant="pill" size="pill" className={inertBtn}>
            Start process
          </Button>
          {modelerHref ? (
            <Button asChild variant="pill-dark" size="pill">
              <Link to={modelerHref} className="no-underline">
                <Pencil className="size-[15px]" strokeWidth={2} aria-hidden />
                Open in modeler
              </Link>
            </Button>
          ) : (
            <Button type="button" disabled variant="pill-dark" size="pill" className={inertBtn}>
              <Pencil className="size-[15px]" strokeWidth={2} aria-hidden />
              Open in modeler
            </Button>
          )}
          <Button type="button" disabled variant="pill-outline" size="pill" className={inertBtn}>
            Save as template
          </Button>
          {/* Not converted to Button: no existing icon size matches this
              circular button's 38px exactly (icon-lg is 36px), and changing
              it risks an unverified 2px visual diff — see this ticket's
              resolution. */}
          <button
            type="button"
            disabled
            aria-label="More actions"
            className={cn(
              'flex size-[38px] items-center justify-center rounded-full border border-border bg-card',
              inertBtn,
            )}
          >
            <MoreVertical className="size-4 text-muted-foreground" strokeWidth={2.4} />
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-3.5 gap-y-2.5">
        <Link
          to={groupHref}
          className="inline-flex max-w-full items-center gap-1.5 text-[12.5px] text-info no-underline"
        >
          <Folder className="size-3.5 shrink-0" strokeWidth={1.8} />
          <span className="min-w-0 truncate">{detail.group_display_name || detail.group_id}</span>
        </Link>
      </div>

      {detail.description ? (
        <p className="mb-[18px] max-w-[820px] text-[14.5px] leading-normal text-muted-foreground">
          {detail.description}
        </p>
      ) : null}

      <div
        className="mb-[18px] grid min-w-0 grid-cols-2 overflow-hidden rounded-[14px] border border-border sm:grid-cols-3 lg:grid-cols-5"
        style={{ gap: 1, background: 'var(--border)' }}
      >
        <KeyNumber label="Last run" value={formatRelativeTime(detail.last_run_in_seconds)} />
        <KeyNumber label="Running now" value={String(detail.running_now)} mono />
        <KeyNumber label="Runs 30d" value={String(detail.runs_30d)} mono />
        <KeyNumber label="Median time" value="—" mono placeholder />
        <KeyNumber label="Errors 30d" value="—" mono placeholder />
      </div>

      <div className="mb-[22px] grid grid-cols-1 gap-x-7 gap-y-3.5 rounded-[14px] border border-border bg-card px-[22px] py-[18px] shadow-xs sm:grid-cols-2">
        <Fact label="Group">
          <Link to={groupHref} className="min-w-0 break-words no-underline">
            {detail.group_display_name || detail.group_id}
          </Link>
        </Fact>
        <Fact label="Identifier">
          <span className="font-mono text-xs break-all">{detail.id}</span>
        </Fact>
      </div>

      <div className="mb-[18px] flex flex-wrap items-center gap-2">
        <a
          href="#instances"
          className="rounded-full border border-border px-3.5 py-1.5 text-[12.5px] font-semibold text-foreground no-underline"
        >
          Instances
        </a>
        <a
          href="#files"
          className="rounded-full border border-border px-3.5 py-1.5 text-[12.5px] font-semibold text-foreground no-underline"
        >
          Files ({detail.files.length})
        </a>
      </div>

      <Card id="instances" variant="bordered" className="mb-[22px] overflow-x-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-[22px] py-4">
          <h2 className="text-[15px] font-semibold text-foreground">Recent instances</h2>
          <Link
            to={viewAllHref}
            className="text-[12.5px] font-semibold text-info no-underline hover:underline"
          >
            {viewAllLabel}
          </Link>
        </div>
        <div
          className={cn(
            'grid min-w-[620px] gap-3 bg-muted/60 px-[22px] py-2.5',
            'text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
            'grid-cols-[minmax(70px,90px)_minmax(120px,1fr)_minmax(0,120px)_minmax(0,100px)_minmax(0,140px)]',
          )}
        >
          <div>ID</div>
          <div>Started by</div>
          <div>Start</div>
          <div>Duration</div>
          <div>Status</div>
        </div>
        {detail.recent_instances.length === 0 ? (
          <p className="border-t border-border px-[22px] py-8 text-center text-[13.5px] text-muted-foreground">
            No instances yet.
          </p>
        ) : (
          detail.recent_instances.map((row) => (
            <div
              key={row.id}
              className={cn(
                'grid min-w-[620px] items-center gap-3 border-t border-border px-[22px] py-3',
                'grid-cols-[minmax(70px,90px)_minmax(120px,1fr)_minmax(0,120px)_minmax(0,100px)_minmax(0,140px)]',
              )}
            >
              <Link
                to={`/process-instances/${row.id}`}
                className="font-mono text-[13px] text-info no-underline hover:underline"
              >
                {row.id}
              </Link>
              <div className="truncate text-[13.5px] text-foreground">{row.started_by || '—'}</div>
              <div className="whitespace-nowrap text-[13px] text-muted-foreground">
                {formatRelativeTime(row.start_in_seconds)}
              </div>
              <div className="font-mono text-[13px] text-muted-foreground">
                {formatDuration(row.duration_seconds)}
              </div>
              <div>
                <StatusBadge status={row.status} />
              </div>
            </div>
          ))
        )}
      </Card>

      <Card id="files" variant="bordered" className="mb-[22px]">
        <div className="px-[22px] pt-4 pb-5">
          <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-[15px] font-semibold text-foreground">Files</h2>
              <p className="mt-0.5 text-[12.5px] text-muted-foreground">BPMN, form schema and UI schema</p>
            </div>
            <Button
              type="button"
              disabled
              variant="pill-outline"
              size="pill"
              className={cn(inertBtn, 'gap-1.5 px-3.5 py-1.5 text-xs')}
            >
              <Plus className="size-3.5" strokeWidth={2.2} aria-hidden />
              Add file
            </Button>
          </div>
          <div className="overflow-hidden rounded-xl border border-border">
            {detail.files.length === 0 ? (
              <p className="px-4 py-8 text-center text-[13.5px] text-muted-foreground">No files yet.</p>
            ) : (
              detail.files.map((file) => (
                <FileRow key={file.name} file={file} modelId={detail.id} tenantId={tenantId} />
              ))
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function KeyNumber({
  label,
  value,
  mono,
  placeholder,
}: {
  label: string;
  value: string;
  mono?: boolean;
  placeholder?: boolean;
}) {
  return (
    <div className="bg-card px-[18px] py-3.5">
      <div className="text-[11px] tracking-[0.05em] text-muted-foreground uppercase">{label}</div>
      <div
        className={cn(
          'mt-1.5 text-base font-semibold whitespace-nowrap',
          mono && 'font-mono font-bold',
          placeholder ? 'text-muted-foreground' : 'text-foreground',
        )}
      >
        {value}
      </div>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 gap-2.5 text-[13px]">
      <span className="w-[78px] shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0">{children}</span>
    </div>
  );
}
