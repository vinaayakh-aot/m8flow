import { useEffect, useMemo, useState } from 'react';
import { Folder, Plus, Search, X } from 'lucide-react';
import { Dialog as DialogPrimitive } from 'radix-ui';

import type { ProcessGroupListItem } from '@/lib/api';
import { Dialog, DialogOverlay, DialogPortal } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { formatRelativeTime } from '@/lib/relativeTime';
import { cn } from '@/lib/utils';

export type ProcessGroupsPickerProps = {
  open: boolean;
  groups: ProcessGroupListItem[];
  loading?: boolean;
  error?: string | null;
  /** Active `?group=` id; null means All groups is selected. */
  selectedGroupId?: string | null;
  onClose: () => void;
  onSelectAll: () => void;
  onSelectGroup: (groupId: string) => void;
};

/**
 * Process groups modal from Processes.dc.html: search, All groups row,
 * group rows, chrome-only New group. Parent owns fetch and `?group=`.
 */
export function ProcessGroupsPicker({
  open,
  groups,
  loading = false,
  error = null,
  selectedGroupId = null,
  onClose,
  onSelectAll,
  onSelectGroup,
}: ProcessGroupsPickerProps) {
  const [search, setSearch] = useState('');

  // Escape-to-close and click-outside-to-close used to be hand-rolled here
  // (a `window` keydown listener plus a backdrop `onClick`) — both are now
  // Radix Dialog's own built-in behavior (wired below via `onOpenChange`),
  // so this effect is left with just its other job: clearing the search box
  // between opens.
  useEffect(() => {
    if (!open) {
      setSearch('');
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      return groups;
    }
    return groups.filter(
      (g) =>
        g.display_name.toLowerCase().includes(q) ||
        g.id.toLowerCase().includes(q) ||
        (g.description || '').toLowerCase().includes(q),
    );
  }, [groups, search]);

  const totalModels = groups.reduce((sum, g) => sum + g.model_count, 0);
  const allSelected = !selectedGroupId;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogPortal>
        {/* Escape and outside-click dismissal are Radix's own built-in
            Dialog behavior now (see the removed `useEffect` above) — both
            funnel through `onOpenChange` into `onClose` the same as the
            Close button. `DialogPrimitive.Content` (used directly rather
            than the shared `DialogContent` wrapper) carries its own
            fixed/top/left positioning replicating this dialog's original
            top-anchored, 720px-wide layout — the shared wrapper's default
            positioning is a centered, small (`max-w-sm`) modal, which
            doesn't fit this page's mockup-matched design. `overlayClassName`
            (added to the shared primitive for this ticket) supplies this
            dialog's own overlay tint, since shadcn's default doesn't match
            either. */}
        <DialogOverlay className="z-40 bg-[rgba(44,55,60,0.40)]" />
        <DialogPrimitive.Content
          aria-labelledby="process-groups-title"
          className="fixed top-[72px] left-1/2 z-40 flex max-h-[calc(100vh-96px)] w-[calc(100%-3rem)] max-w-[720px] -translate-x-1/2 flex-col overflow-hidden rounded-2xl bg-card shadow-lg outline-none"
        >
          <div className="flex shrink-0 items-start justify-between gap-4 px-6 pt-[22px]">
            <div className="min-w-0">
              <h2 id="process-groups-title" className="text-[22px] font-semibold text-foreground">
                Process groups
              </h2>
              <p className="mt-1 text-[13.5px] text-muted-foreground">
                Pick a group to filter the model list, or manage groups here.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="flex size-[34px] shrink-0 items-center justify-center rounded-full border border-border bg-card"
            >
              <X className="size-3.5 text-muted-foreground" strokeWidth={2.4} />
            </button>
          </div>

          <div className="shrink-0 px-6 pt-4 pb-3">
            <label className="flex items-center gap-2.5 rounded-full border border-border bg-muted px-4 py-2.5">
              <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
              <Input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={`Search ${groups.length} groups`}
                className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] text-foreground shadow-none outline-none focus-visible:ring-0"
                aria-label="Search groups"
              />
            </label>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-2">
            {error ? (
              <p className="px-3 py-2 text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
            {loading ? (
              <p className="px-3 py-4 text-sm text-muted-foreground">Loading groups…</p>
            ) : null}

            {!loading ? (
              <button
                type="button"
                onClick={onSelectAll}
                className={cn(
                  'flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left',
                  allSelected
                    ? 'border border-nav-active/40 bg-nav-active/10'
                    : 'border border-transparent',
                )}
              >
                <span className="flex-1 text-sm font-semibold text-foreground">All groups</span>
                <span className="font-mono text-xs text-muted-foreground">{totalModels}</span>
              </button>
            ) : null}

            {!loading &&
              filtered.map((group) => {
                const selected = selectedGroupId === group.id;
                return (
                  <button
                    key={group.id}
                    type="button"
                    onClick={() => onSelectGroup(group.id)}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left',
                      selected
                        ? 'border border-nav-active/40 bg-nav-active/10'
                        : 'border border-transparent',
                    )}
                  >
                    <span className="flex size-[30px] shrink-0 items-center justify-center rounded-lg bg-muted">
                      <Folder className="size-[15px] text-muted-foreground" strokeWidth={1.8} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-foreground">
                        {group.display_name || group.id}
                      </span>
                      <span className="mt-0.5 block truncate text-[12.5px] text-muted-foreground">
                        {group.description || group.id}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-3">
                      <span className="whitespace-nowrap text-xs text-muted-foreground">
                        {group.last_run_in_seconds == null
                          ? 'No runs yet'
                          : formatRelativeTime(group.last_run_in_seconds)}
                      </span>
                      <span className="rounded-full bg-muted px-2.5 py-0.5 font-mono text-xs text-muted-foreground">
                        {group.model_count}
                      </span>
                    </span>
                  </button>
                );
              })}
          </div>

          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-3.5">
            <span className="text-[12.5px] text-muted-foreground">
              {groups.length} group{groups.length === 1 ? '' : 's'} in this tenant
            </span>
            <button
              type="button"
              aria-disabled="true"
              className="inline-flex cursor-default items-center gap-1.5 rounded-full border-2 border-border px-4 py-1.5 text-xs font-semibold tracking-[0.04em] text-foreground uppercase select-none"
            >
              <Plus className="size-3.5" strokeWidth={2.2} />
              New group
            </button>
          </div>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
