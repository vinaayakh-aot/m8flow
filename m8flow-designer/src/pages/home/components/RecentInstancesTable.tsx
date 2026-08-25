import { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

import { fetchHomeRecentInstances, type HomeRecentInstance } from '@/lib/api';
import { formatRelativeTime } from '@/lib/relativeTime';
import { StatusBadge } from '@/components/StatusBadge';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export type RecentInstancesTableProps = {
  tenantId?: string | null;
  /** When set, skip the network fetch (prototype / tests). */
  rows?: HomeRecentInstance[] | null;
};

/**
 * Home "Recent process instances" table — Tenant / ID / Process / Started /
 * Status + a link to that instance's detail page. "View all" links to the
 * unfiltered Process Instances list (Process Instances + task-state map,
 * ticket 04 capstone — both were inert until that map's own
 * `/process-instances`(+`/:id`) routes existed).
 */
export function RecentInstancesTable({
  tenantId = null,
  rows: rowsOverride,
}: RecentInstancesTableProps) {
  const [rows, setRows] = useState<HomeRecentInstance[]>(rowsOverride ?? []);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(rowsOverride === undefined);

  useEffect(() => {
    if (rowsOverride !== undefined) {
      setRows(rowsOverride ?? []);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchHomeRecentInstances(tenantId)
      .then((payload) => {
        if (!cancelled) {
          setRows(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load instances');
          setRows([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tenantId, rowsOverride]);

  return (
    <Card variant="bordered" className="overflow-hidden">
      <div className="flex items-center justify-between px-[22px] py-[18px]">
        <h2 className="text-[15px] font-semibold text-foreground">Recent process instances</h2>
        <Link
          to="/process-instances"
          className="text-[13px] font-semibold text-info no-underline hover:underline"
        >
          View all
        </Link>
      </div>

      {error ? (
        <p className="border-t border-border px-[22px] py-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="overflow-x-auto" aria-busy={loading}>
        <div
          className={cn(
            'grid min-w-[640px] gap-3 px-[22px] py-2.5 text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
            'grid-cols-[110px_64px_minmax(0,1fr)_110px_150px_40px]',
          )}
        >
          <div>Tenant</div>
          <div>ID</div>
          <div>Process</div>
          <div>Started</div>
          <div>Status</div>
          <div />
        </div>

        {loading ? (
          <div className="border-t border-border px-[22px] py-4 text-sm text-muted-foreground">
            Loading…
          </div>
        ) : null}

        {!loading && rows.length === 0 && !error ? (
          <div className="border-t border-border px-[22px] py-4 text-sm text-muted-foreground">
            No recent process instances.
          </div>
        ) : null}

        {rows.map((row) => (
          <div
            key={row.id}
            className={cn(
              'grid min-w-[640px] items-center gap-3 border-t border-border px-[22px] py-3.5',
              'grid-cols-[110px_64px_minmax(0,1fr)_110px_150px_40px]',
            )}
          >
            <div className="truncate text-[13.5px] text-foreground">{row.tenant_name}</div>
            <div className="font-mono text-[13px] text-muted-foreground">{row.id}</div>
            <div className="truncate text-[13.5px] text-foreground">
              {row.process_model_display_name}
            </div>
            <div className="text-[13px] text-muted-foreground">
              {formatRelativeTime(row.start_in_seconds)}
            </div>
            <div>
              <StatusBadge status={row.status} />
            </div>
            <div className="flex justify-end">
              <Link
                to={`/process-instances/${row.id}`}
                title="Open instance"
                aria-label={`Open instance ${row.id}`}
                className="flex size-7 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <ExternalLink className="size-[15px]" aria-hidden />
              </Link>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
