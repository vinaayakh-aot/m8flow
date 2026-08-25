import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from 'react';
import { ExternalLink, Folder, MoreVertical, Plus, Search, Trash2 } from 'lucide-react';

import { ApiError, type ProcessModelListItem } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { formatRelativeTime } from '@/lib/relativeTime';
import { cn } from '@/lib/utils';

export type ProcessesModelsListProps = {
  models: ProcessModelListItem[];
  loading?: boolean;
  error?: string | null;
  /** Active group filter id from `?group=`; null = all groups. */
  groupFilter?: string | null;
  /** Label for the scope pill (group display name or id). */
  scopeLabel?: string;
  /** Total models before client search (for empty-state copy). */
  totalUnfilteredCount?: number;
  onBrowseGroups?: () => void;
  onClearGroupFilter?: () => void;
  onOpenModel?: (model: ProcessModelListItem) => void;
  onFilterByGroup?: (groupId: string) => void;
  /** Starts an instance from the model; parent handles navigation. */
  onStartModel?: (model: ProcessModelListItem) => void;
  /** Deletes the model. Should reject (throw) on failure so the confirmation
   * dialog can surface the reason (e.g. a 409 when instances still exist). */
  onDeleteModel?: (model: ProcessModelListItem) => Promise<void> | void;
};

type SortDir = 'desc' | 'asc';

/**
 * Processes models list — matches Processes.dc.html list surface.
 * Presentational: parent owns fetch, tenant gating, and navigation.
 */
export function ProcessesModelsList({
  models,
  loading = false,
  error = null,
  groupFilter = null,
  scopeLabel = 'All groups',
  totalUnfilteredCount,
  onBrowseGroups,
  onClearGroupFilter,
  onOpenModel,
  onFilterByGroup,
  onStartModel,
  onDeleteModel,
}: ProcessesModelsListProps) {
  const [search, setSearch] = useState('');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const searchRef = useRef<HTMLInputElement>(null);

  // Delete confirmation dialog state.
  const [deleteTarget, setDeleteTarget] = useState<ProcessModelListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function confirmDelete() {
    if (!deleteTarget || !onDeleteModel) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDeleteModel(deleteTarget);
      setDeleteTarget(null);
    } catch (err: unknown) {
      // A 409 means the model still has instances (the backend's block) —
      // give that its own message rather than a generic failure.
      if (err instanceof ApiError && err.status === 409) {
        setDeleteError(
          'This process model still has process instances and can’t be deleted. ' +
            'Remove or finish its instances first.',
        );
      } else {
        setDeleteError(err instanceof Error ? err.message : 'Failed to delete process model');
      }
    } finally {
      setDeleting(false);
    }
  }

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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = models;
    if (q) {
      rows = rows.filter(
        (m) =>
          m.display_name.toLowerCase().includes(q) ||
          m.id.toLowerCase().includes(q) ||
          m.group_display_name.toLowerCase().includes(q) ||
          m.group_id.toLowerCase().includes(q),
      );
    }
    const sorted = [...rows].sort((a, b) => {
      const aVal = a.last_run_in_seconds ?? -1;
      const bVal = b.last_run_in_seconds ?? -1;
      return sortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });
    return sorted;
  }, [models, search, sortDir]);

  const resultCount = `${filtered.length} model${filtered.length === 1 ? '' : 's'}`;
  const totalForEmpty = totalUnfilteredCount ?? models.length;
  const groupFilterOn = Boolean(groupFilter);
  const isEmpty = !loading && !error && filtered.length === 0;

  function stopRowNav(event: MouseEvent) {
    event.stopPropagation();
  }

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setSearch('');
      searchRef.current?.blur();
    }
  }

  return (
    <>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-[32px] font-semibold tracking-tight text-foreground">Processes</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {/* "Browse groups" removed — the "Showing [scope] ▾" pill below opens
              the same group picker, so a second entry point was redundant. */}
          {/* Not converted to Button: this "coming soon" chrome uses
              aria-disabled (not the native disabled attribute) to stay
              focusable-but-inert — Button's disabled: styling hooks key off
              the real attribute, so they wouldn't engage here anyway. Left
              as-is rather than force a native `disabled` that would change
              its focus/interaction semantics — see this ticket's
              resolution. */}
          <button
            type="button"
            aria-disabled="true"
            className="inline-flex cursor-default items-center gap-2 rounded-full bg-nav-active px-5 py-2.5 text-[12.5px] font-semibold tracking-[0.04em] text-foreground uppercase shadow-xs select-none"
          >
            <Plus className="size-[15px]" strokeWidth={2.2} />
            New process model
          </button>
        </div>
      </div>

      <div className="mt-1.5 mb-[22px] flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>Showing</span>
        <button
          type="button"
          onClick={onBrowseGroups}
          className={cn(
            'inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1.5 text-[13.5px] font-semibold text-foreground',
            groupFilterOn
              ? 'border-nav-active/40 bg-nav-active/15'
              : 'border-border bg-card',
          )}
        >
          <Folder className="size-3.5 shrink-0" strokeWidth={1.8} />
          <span className="min-w-0 truncate">{scopeLabel}</span>
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="shrink-0"
            aria-hidden
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        {groupFilterOn ? (
          <button
            type="button"
            onClick={onClearGroupFilter}
            className="px-1 text-[13px] text-info"
          >
            Clear
          </button>
        ) : null}
      </div>

      <div className="pb-14">
        <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
          <label className="flex max-w-[420px] min-w-0 flex-1 items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2.5">
            <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
            <Input
              ref={searchRef}
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={onSearchKeyDown}
              placeholder="Search process models"
              className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] text-foreground shadow-none outline-none focus-visible:ring-0"
              aria-label="Search process models"
            />
            <kbd className="shrink-0 rounded-md border border-border px-1.5 py-px font-mono text-[11px] text-muted-foreground">
              ⌘K
            </kbd>
          </label>

          <button
            type="button"
            aria-disabled="true"
            className="inline-flex cursor-default items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-2 text-[13px] font-medium text-muted-foreground select-none"
          >
            Any status
            <ChevronDown />
          </button>
          <button
            type="button"
            aria-disabled="true"
            className="inline-flex cursor-default items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-2 text-[13px] font-medium text-muted-foreground select-none"
          >
            All owners
            <ChevronDown />
          </button>
          <button
            type="button"
            onClick={() => setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-2 text-[13px] font-medium text-foreground"
            aria-label={`Sort by last run, currently ${sortDir === 'desc' ? 'newest first' : 'oldest first'}`}
          >
            Sort: last run {sortDir === 'desc' ? '↓' : '↑'}
            <ChevronDown />
          </button>

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
              'grid min-w-[760px] gap-4 border-b border-border bg-muted/60 px-[22px] py-3',
              'text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
              'grid-cols-[minmax(220px,2.4fr)_minmax(0,140px)_minmax(0,90px)_minmax(0,130px)_minmax(0,190px)]',
            )}
          >
            <div>Process model</div>
            <div>Status</div>
            <div>Runs 30d</div>
            <div>Last run</div>
            <div className="text-right">Actions</div>
          </div>

          {loading ? (
            <div className="px-[22px] py-8 text-sm text-muted-foreground">Loading process models…</div>
          ) : null}

          {isEmpty ? (
            <div className="px-6 py-[52px] text-center">
              <div className="text-[15.5px] font-semibold text-foreground">
                {groupFilterOn ? 'No models in this group' : 'No process models'}
              </div>
              <p className="mt-2 mb-5 text-[13.5px] text-muted-foreground">
                {groupFilterOn
                  ? `Create a model here, or clear the filter to see all ${totalForEmpty} models.`
                  : search.trim()
                    ? 'Try a different search, or clear the search box.'
                    : 'No models are available for this tenant yet.'}
              </p>
              <div className="flex flex-wrap items-center justify-center gap-2.5">
                {/* Not converted to Button: aria-disabled chrome, same
                    reasoning as the header's "New process model" above. */}
                <button
                  type="button"
                  aria-disabled="true"
                  className="cursor-default rounded-full bg-nav-active px-5 py-2.5 text-xs font-semibold tracking-[0.04em] text-foreground uppercase select-none"
                >
                  New process model
                </button>
                {groupFilterOn ? (
                  <Button
                    type="button"
                    variant="pill-outline"
                    size="pill"
                    onClick={onClearGroupFilter}
                    className="text-xs"
                  >
                    Clear filter
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          {!loading &&
            filtered.map((model) => (
              <div
                key={model.id}
                role="button"
                tabIndex={0}
                onClick={() => onOpenModel?.(model)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onOpenModel?.(model);
                  }
                }}
                className={cn(
                  'grid min-w-[760px] cursor-pointer items-center gap-4 border-b border-border px-[22px] py-[15px]',
                  'grid-cols-[minmax(220px,2.4fr)_minmax(0,140px)_minmax(0,90px)_minmax(0,130px)_minmax(0,190px)]',
                )}
              >
                <div className="min-w-0">
                  <div className="line-clamp-2 text-[14.5px] leading-snug font-semibold text-foreground">
                    {model.display_name}
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      stopRowNav(e);
                      onFilterByGroup?.(model.group_id);
                    }}
                    className="mt-1 flex max-w-full items-center gap-1.5 text-left text-[12.5px] text-muted-foreground"
                  >
                    <Folder className="size-3.5 shrink-0" strokeWidth={1.8} />
                    <span className="truncate">
                      {model.group_display_name || model.group_id}
                    </span>
                  </button>
                </div>
                <div>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground">
                    —
                  </span>
                </div>
                <div className="font-mono text-[13px] text-muted-foreground">{model.runs_30d}</div>
                <div className="whitespace-nowrap text-[13px] text-muted-foreground">
                  {formatRelativeTime(model.last_run_in_seconds)}
                </div>
                <div
                  className="flex items-center justify-end gap-2"
                  onClick={stopRowNav}
                  onKeyDown={(e) => e.stopPropagation()}
                >
                  {/* Start is only rendered for users who can manage processes
                      (parent passes onStartModel); others don't see it rather
                      than get a button that 403s. */}
                  {onStartModel ? (
                    <Button
                      type="button"
                      variant="pill"
                      size="pill"
                      onClick={() => onStartModel(model)}
                      className="px-3.5 py-1.5 text-[11.5px] shadow-none"
                    >
                      Start
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="pill-outline"
                    size="pill"
                    onClick={() => onOpenModel?.(model)}
                    className="border px-3.5 py-1.5 text-[11.5px]"
                  >
                    Open
                  </Button>
                  <RowActionsMenu
                    onOpen={() => onOpenModel?.(model)}
                    onDelete={onDeleteModel ? () => setDeleteTarget(model) : undefined}
                  />
                </div>
              </div>
            ))}

          {!loading && !isEmpty ? (
            <div className="flex flex-wrap items-center justify-between gap-3 px-[22px] py-3.5 text-[13px] text-muted-foreground">
              <span>{resultCount}</span>
              <span className="flex items-center gap-2.5">
                <span>Rows per page: 25</span>
                <span className="font-mono">
                  1–{filtered.length}
                </span>
              </span>
            </div>
          ) : null}
        </Card>
      </div>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) {
            setDeleteTarget(null);
            setDeleteError(null);
          }
        }}
      >
        <DialogContent showCloseButton={!deleting}>
          <DialogHeader>
            <DialogTitle>Delete process model?</DialogTitle>
            <DialogDescription>
              {deleteTarget ? (
                <>
                  This permanently deletes{' '}
                  <span className="font-semibold text-foreground">{deleteTarget.display_name}</span>{' '}
                  and its files. This can’t be undone.
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          {deleteError ? (
            <p className="text-sm text-destructive" role="alert">
              {deleteError}
            </p>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setDeleteTarget(null);
                setDeleteError(null);
              }}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleting}
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Working per-row overflow menu for the Processes list. Self-contained
 * open state + outside-click/Escape close (the app has no shared
 * DropdownMenu primitive). "Delete" is only offered when the parent wires
 * onDelete; it opens the list's confirmation dialog rather than deleting
 * directly. */
function RowActionsMenu({
  onOpen,
  onDelete,
}: {
  onOpen: () => void;
  onDelete?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(event: globalThis.MouseEvent) {
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

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-label="More actions"
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
          className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-xl border border-border bg-card py-1 shadow-lg"
        >
          <RowMenuItem
            icon={<ExternalLink className="size-3.5" />}
            label="Open"
            onSelect={() => {
              setOpen(false);
              onOpen();
            }}
          />
          {onDelete ? (
            <RowMenuItem
              icon={<Trash2 className="size-3.5" />}
              label="Delete"
              destructive
              onSelect={() => {
                setOpen(false);
                onDelete();
              }}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function RowMenuItem({
  icon,
  label,
  onSelect,
  destructive = false,
}: {
  icon: ReactNode;
  label: string;
  onSelect: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onSelect}
      className={cn(
        'flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px] hover:bg-muted',
        destructive ? 'text-destructive' : 'text-foreground',
      )}
    >
      <span className={destructive ? 'text-destructive' : 'text-muted-foreground'}>{icon}</span>
      {label}
    </button>
  );
}

function ChevronDown() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}
