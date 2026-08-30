import { useEffect, useState } from 'react';

import {
  fetchProcessInstanceMilestones,
  type ProcessInstanceMilestoneRow,
} from '@/lib/processInstancesApi';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export type ProcessInstanceMilestonesTableProps = {
  instanceId: number;
  tenantId?: string | null;
  /** When set, skip the network fetch (page-shell prototype / tests). */
  milestones?: ProcessInstanceMilestoneRow[] | null;
};

const GRID_COLS = 'grid-cols-[minmax(120px,1.4fr)_minmax(200px,2.6fr)_minmax(0,180px)]';
const GRID_MIN_WIDTH = 'min-w-[700px]';

function cell(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : '—';
}

function formatMilestoneTimestamp(epochSeconds: number | null | undefined): string {
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

/**
 * Milestones tab body: zero or one current last milestone — not a history.
 * GET /v1.0/m8flow/process-instances/{id}/milestones. Timestamp is plain text.
 */
export function ProcessInstanceMilestonesTable({
  instanceId,
  tenantId = null,
  milestones: milestonesOverride,
}: ProcessInstanceMilestonesTableProps) {
  const [milestones, setMilestones] = useState<ProcessInstanceMilestoneRow[]>(
    milestonesOverride ?? [],
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(milestonesOverride === undefined);

  useEffect(() => {
    if (milestonesOverride !== undefined) {
      setMilestones(milestonesOverride ?? []);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchProcessInstanceMilestones(instanceId, tenantId)
      .then((payload) => {
        if (!cancelled) setMilestones(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load milestones');
          setMilestones([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [instanceId, tenantId, milestonesOverride]);

  return (
    <Card variant="bordered" className="overflow-x-auto">
      <div
        className={cn(
          'grid gap-4 border-b border-border bg-muted/60 px-[22px] py-3',
          'text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
          GRID_MIN_WIDTH,
          GRID_COLS,
        )}
      >
        <div>Milestone</div>
        <div>Bpmn process</div>
        <div>Timestamp</div>
      </div>

      {error ? (
        <p className="px-[22px] py-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="px-[22px] py-8 text-sm text-muted-foreground" aria-busy="true">
          Loading milestones…
        </p>
      ) : null}

      {!loading &&
        milestones.map((row) => (
          <div
            key={row.milestone}
            className={cn(
              'grid items-center gap-4 border-b border-border px-[22px] py-[14px]',
              GRID_MIN_WIDTH,
              GRID_COLS,
            )}
          >
            <div className="text-[14px] font-semibold text-foreground">{row.milestone}</div>
            <div className="min-w-0 break-all font-mono text-[12.5px] text-muted-foreground">
              {cell(row.bpmn_process)}
            </div>
            <time
              className="font-mono text-[12.5px] text-foreground"
              dateTime={row.timestamp != null ? new Date(row.timestamp * 1000).toISOString() : undefined}
            >
              {formatMilestoneTimestamp(row.timestamp)}
            </time>
          </div>
        ))}
    </Card>
  );
}
