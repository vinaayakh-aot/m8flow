import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight, Copy, ExternalLink, Link2, MoreVertical, Search } from 'lucide-react';

import type { ProcessInstanceListItem, ProcessInstanceSort } from '@/lib/processInstancesApi';
import { StatusBadge } from '@/components/StatusBadge';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { formatDuration } from '@/pages/process-model-detail/components/ProcessModelOverview';
import { formatRelativeTime } from '@/lib/relativeTime';
import { cn } from '@/lib/utils';

export type ProcessInstancesListProps = {
  instances: ProcessInstanceListItem[];
  loading?: boolean;
  error?: string | null;
  search: string;
  onSearchChange: (value: string) => void;
  status: string;
  onStatusChange: (value: string) => void;
  owners: string[];
  startedBy: string;
  onStartedByChange: (value: string) => void;
  sort: ProcessInstanceSort;
  onSortChange: (value: ProcessInstanceSort) => void;
  page: number;
  pageCount: number;
  perPage: number;
  onPerPageChange: (value: number) => void;
  totalCount: number;
  onPageChange: (page: number) => void;
  onOpenInstance?: (instance: ProcessInstanceListItem) => void;
};

/** No mockup exists for a standalone Process Instances page (it appears
 * only as the "Recent instances" table inside a process model's detail in
 * Processes.dc.html). This table mirrors that column shape plus the app's
 * other tabular lists (ProcessesModelsList.tsx) — instance rows are
 * report-style data (status/timing columns), not browsable content. */
const STATUS_OPTIONS = [
  { value: '', label: 'Any status' },
  { value: 'running', label: 'Running' },
  { value: 'waiting', label: 'Waiting' },
  { value: 'user_input_required', label: 'User Input Required' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'complete', label: 'Complete' },
  { value: 'error', label: 'Error' },
  { value: 'terminated', label: 'Terminated' },
  { value: 'not_started', label: 'Not Started' },
];

// Values must match the backend allowlist (workflow.py `_INSTANCE_SORTS`);
// the union type on onSortChange keeps them honest.
const SORT_OPTIONS: { value: ProcessInstanceSort; label: string }[] = [
  { value: 'newest', label: 'Sort: Newest' },
  { value: 'oldest', label: 'Sort: Oldest' },
  { value: 'recent_start', label: 'Sort: Recent start' },
  { value: 'status', label: 'Sort: Status' },
];

const PER_PAGE_OPTIONS = [25, 50, 100];

const CHIP_SELECT_CLASS =
  'appearance-none rounded-full border border-border bg-card py-2 pr-8 pl-3.5 text-[13px] font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-nav-active/40';

const GRID_COLS =
  'grid-cols-[64px_minmax(200px,2fr)_130px_120px_130px_100px_44px]';
const GRID_MIN_WIDTH = 'min-w-[804px]';

export function ProcessInstancesList({
  instances,
  loading = false,
  error = null,
  search,
  onSearchChange,
  status,
  onStatusChange,
  owners,
  startedBy,
  onStartedByChange,
  sort,
  onSortChange,
  page,
  pageCount,
  perPage,
  onPerPageChange,
  totalCount,
  onPageChange,
  onOpenInstance,
}: ProcessInstancesListProps) {
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      onSearchChange('');
      searchRef.current?.blur();
    }
  }

  const resultCount = `${totalCount} instance${totalCount === 1 ? '' : 's'}`;
  const isEmpty = !loading && !error && instances.length === 0;

  // "1–N of total" range for the footer (Processes.dc.html:230). Clamp so a
  // stale page number never renders a nonsensical range while data reloads.
  const rangeStart = totalCount === 0 ? 0 : (page - 1) * perPage + 1;
  const rangeEnd = Math.min(page * perPage, totalCount);

  return (
    <>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-[32px] font-semibold tracking-tight text-foreground">Process Instances</h1>
        </div>
      </div>

      <div className="pb-14">
        <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
          <label className="flex max-w-[420px] min-w-0 flex-1 items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2.5">
            <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
            <Input
              ref={searchRef}
              type="search"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              onKeyDown={onSearchKeyDown}
              placeholder="Search by process model"
              className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] text-foreground shadow-none outline-none focus-visible:ring-0"
              aria-label="Search process instances"
            />
            <kbd className="shrink-0 rounded-md border border-border px-1.5 py-px font-mono text-[11px] text-muted-foreground">
              ⌘K
            </kbd>
          </label>

          <label className="relative">
            <span className="sr-only">Status</span>
            <select
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              className={CHIP_SELECT_CLASS}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="relative">
            <span className="sr-only">Started by</span>
            <select
              value={startedBy}
              onChange={(e) => onStartedByChange(e.target.value)}
              className={CHIP_SELECT_CLASS}
              aria-label="Filter by who started the instance"
            >
              <option value="">All owners</option>
              {owners.map((owner) => (
                <option key={owner} value={owner}>
                  {owner}
                </option>
              ))}
            </select>
          </label>

          <label className="relative">
            <span className="sr-only">Sort</span>
            <select
              value={sort}
              onChange={(e) => onSortChange(e.target.value as ProcessInstanceSort)}
              className={CHIP_SELECT_CLASS}
              aria-label="Sort instances"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <div className="ml-auto whitespace-nowrap text-[13px] text-muted-foreground">
            {loading ? 'Loading…' : resultCount}
          </div>
        </div>

        {error ? (
          <p className="mb-4 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        <Card variant="bordered" className="overflow-x-auto">
          <div
            className={cn(
              'grid gap-4 border-b border-border bg-muted/60 px-[22px] py-3',
              'text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
              GRID_MIN_WIDTH,
              GRID_COLS,
            )}
          >
            <div>ID</div>
            <div>Process model</div>
            <div>Status</div>
            <div>Started</div>
            <div>Started by</div>
            <div className="text-right">Duration</div>
            <div className="text-right">
              <span className="sr-only">Actions</span>
            </div>
          </div>

          {loading ? (
            <div className="px-[22px] py-8 text-sm text-muted-foreground">Loading process instances…</div>
          ) : null}

          {isEmpty ? (
            <div className="px-6 py-[52px] text-center">
              <div className="text-[15.5px] font-semibold text-foreground">No process instances</div>
              <p className="mt-2 text-[13.5px] text-muted-foreground">
                {search.trim() || status || startedBy
                  ? 'Try a different search or clear the filters.'
                  : 'No process instances have run for this tenant yet.'}
              </p>
            </div>
          ) : null}

          {!loading &&
            instances.map((instance) => (
              <div
                key={instance.id}
                role="button"
                tabIndex={0}
                onClick={() => onOpenInstance?.(instance)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onOpenInstance?.(instance);
                  }
                }}
                className={cn(
                  'grid cursor-pointer items-center gap-4 border-b border-border px-[22px] py-[15px]',
                  GRID_MIN_WIDTH,
                  GRID_COLS,
                )}
              >
                {/* Link-colored to signal the row is openable (Processes.dc.html
                    styles the instance id in link color); the whole row already
                    navigates via onOpenInstance, so this stays plain text. */}
                <div className="font-mono text-[13px] font-medium text-info">{instance.id}</div>
                <div className="min-w-0 truncate text-[14px] font-medium text-foreground">
                  {instance.process_model_display_name}
                </div>
                <div>
                  <StatusBadge status={instance.status} />
                </div>
                <div className="text-[13px] text-muted-foreground">
                  {formatRelativeTime(instance.start_in_seconds)}
                </div>
                <div className="truncate text-[13px] text-muted-foreground">{instance.started_by || '—'}</div>
                <div className="text-right font-mono text-[13px] text-muted-foreground">
                  {instance.start_in_seconds != null && instance.end_in_seconds != null
                    ? formatDuration(instance.end_in_seconds - instance.start_in_seconds)
                    : '—'}
                </div>
                <div
                  className="flex items-center justify-end"
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => e.stopPropagation()}
                >
                  <RowActionsMenu
                    instance={instance}
                    onOpen={() => onOpenInstance?.(instance)}
                  />
                </div>
              </div>
            ))}

          {!loading && !isEmpty ? (
            <div className="flex flex-wrap items-center justify-between gap-3 px-[22px] py-3.5 text-[13px] text-muted-foreground">
              <span>
                {rangeStart}–{rangeEnd} of {totalCount}
              </span>
              <span className="flex items-center gap-3">
                <label className="flex items-center gap-2">
                  <span>Rows per page</span>
                  <select
                    value={perPage}
                    onChange={(e) => onPerPageChange(Number(e.target.value))}
                    className="appearance-none rounded-md border border-border bg-card py-1 pr-6 pl-2 text-[12.5px] font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-nav-active/40"
                    aria-label="Rows per page"
                  >
                    {PER_PAGE_OPTIONS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <span className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onPageChange(page - 1)}
                    disabled={page <= 1}
                    aria-label="Previous page"
                    className="flex size-7 items-center justify-center rounded-full border border-border disabled:opacity-40"
                  >
                    <ChevronLeft className="size-3.5" />
                  </button>
                  <span className="font-mono">
                    Page {page} of {Math.max(pageCount, 1)}
                  </span>
                  <button
                    type="button"
                    onClick={() => onPageChange(page + 1)}
                    disabled={page >= pageCount}
                    aria-label="Next page"
                    className="flex size-7 items-center justify-center rounded-full border border-border disabled:opacity-40"
                  >
                    <ChevronRight className="size-3.5" />
                  </button>
                </span>
              </span>
            </div>
          ) : null}
        </Card>
      </div>
    </>
  );
}

/** Read-only per-row overflow menu (Processes.dc.html row kebab). Lifecycle
 * actions (suspend/resume/terminate/retry) are deliberately out of scope —
 * they'd require workflow-write endpoints that don't exist yet — so this
 * offers only safe, local actions. Self-contained open state + outside-click/
 * Escape close, since the app has no shared DropdownMenu primitive. */
function RowActionsMenu({
  instance,
  onOpen,
}: {
  instance: ProcessInstanceListItem;
  onOpen: () => void;
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  async function copy(text: string) {
    try {
      await navigator.clipboard?.writeText(text);
    } catch {
      // Clipboard can reject (permissions/insecure context) — a copy action
      // silently failing is acceptable; nothing else depends on it.
    }
    setOpen(false);
  }

  const instanceUrl =
    typeof window !== 'undefined'
      ? `${window.location.origin}/process-instances/${instance.id}`
      : `/process-instances/${instance.id}`;

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-label="Instance actions"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex size-7 items-center justify-center rounded-full hover:bg-muted"
      >
        <MoreVertical className="size-[15px] text-muted-foreground" strokeWidth={2.4} />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-border bg-card py-1 shadow-lg"
        >
          <MenuItem icon={<ExternalLink className="size-3.5" />} label="Open" onSelect={() => { setOpen(false); onOpen(); }} />
          <MenuItem
            icon={<Copy className="size-3.5" />}
            label="Copy instance ID"
            onSelect={() => copy(String(instance.id))}
          />
          <MenuItem
            icon={<Link2 className="size-3.5" />}
            label="Copy link"
            onSelect={() => copy(instanceUrl)}
          />
        </div>
      ) : null}
    </div>
  );
}

function MenuItem({
  icon,
  label,
  onSelect,
}: {
  icon: ReactNode;
  label: string;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onSelect}
      className="flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px] text-foreground hover:bg-muted"
    >
      <span className="text-muted-foreground">{icon}</span>
      {label}
    </button>
  );
}
