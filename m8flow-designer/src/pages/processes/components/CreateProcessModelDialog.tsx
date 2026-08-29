import { useEffect, useState, type FormEvent } from 'react';

import { fetchProcessGroups, type ProcessGroupListItem } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';

export type CreateProcessModelDialogProps = {
  open: boolean;
  onClose: () => void;
  scopedTenantId: string | null;
  /** Prefill from the processes list `?group=` filter. */
  defaultGroupId?: string | null;
  onCreated: (encodedProcessModelId: string) => void;
  onCreate: (input: {
    group_id: string;
    id: string;
    display_name: string;
    description: string;
  }) => Promise<{ id: string }>;
};

export function CreateProcessModelDialog({
  open,
  onClose,
  scopedTenantId,
  defaultGroupId = null,
  onCreated,
  onCreate,
}: CreateProcessModelDialogProps) {
  const [groups, setGroups] = useState<ProcessGroupListItem[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [processGroupId, setProcessGroupId] = useState('');
  const [processModelId, setProcessModelId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    setProcessModelId('');
    setDisplayName('');
    setDescription('');
    setError(null);

    let cancelled = false;
    setGroupsLoading(true);
    fetchProcessGroups(scopedTenantId)
      .then((rows) => {
        if (cancelled) return;
        setGroups(rows);
        const preferred =
          (defaultGroupId && rows.some((g) => g.id === defaultGroupId) && defaultGroupId) ||
          rows[0]?.id ||
          '';
        setProcessGroupId(preferred);
      })
      .catch(() => {
        if (!cancelled) setGroups([]);
      })
      .finally(() => {
        if (!cancelled) setGroupsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, scopedTenantId, defaultGroupId]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!processGroupId || !processModelId.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await onCreate({
        group_id: processGroupId,
        id: processModelId.trim(),
        display_name: displayName.trim(),
        description: description.trim(),
      });
      onCreated(result.id.split('/').join(':'));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create process model');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New process model</DialogTitle>
            <DialogDescription>
              Creates a model under a process group and a default BPMN you can open in the modeler.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="cpm-group" className="text-xs font-medium text-muted-foreground">
              Process group
            </label>
            {groupsLoading ? (
              <p className="text-sm text-muted-foreground">Loading groups…</p>
            ) : groups.length === 0 ? (
              <p className="text-sm text-destructive">
                No process groups exist yet — create one from Process groups first.
              </p>
            ) : (
              <select
                id="cpm-group"
                value={processGroupId}
                onChange={(e) => setProcessGroupId(e.target.value)}
                className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.display_name || g.id}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="cpm-id" className="text-xs font-medium text-muted-foreground">
              Process model ID
            </label>
            <Input
              id="cpm-id"
              value={processModelId}
              onChange={(e) => setProcessModelId(e.target.value)}
              placeholder="invoice-approval"
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="cpm-name" className="text-xs font-medium text-muted-foreground">
              Display name
            </label>
            <Input
              id="cpm-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Invoice Approval"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="cpm-description" className="text-xs font-medium text-muted-foreground">
              Description (optional)
            </label>
            <Input
              id="cpm-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting || groups.length === 0 || !processModelId.trim()}
            >
              {submitting ? 'Creating…' : 'Create process model'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
