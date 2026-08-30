import { useEffect, useState } from 'react';

import {
  fetchProcessInstanceEvents,
  type ProcessInstanceEventRow,
} from '@/lib/processInstancesApi';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export type ProcessInstanceEventsTableProps = {
  instanceId: number;
  tenantId?: string | null;
  /** When set, skip the network fetch (page-shell prototype / tests). */
  events?: ProcessInstanceEventRow[] | null;
};

const GRID_COLS =
  'grid-cols-[minmax(50px,60px)_minmax(200px,2.2fr)_minmax(0,120px)_minmax(0,130px)_minmax(0,130px)_minmax(0,140px)_minmax(0,90px)_minmax(0,150px)]';
const GRID_MIN_WIDTH = 'min-w-[1080px]';

function cell(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : '—';
}

/** UTC `YYYY-MM-DD HH:MM:SS` matching the mockup clock; not a link (target is fog). */
function formatEventTimestamp(epochSeconds: number | null | undefined): string {
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
 * Events tab body for process instance detail. Fetches
 * GET /v1.0/m8flow/process-instances/{id}/events. Timestamp is plain text —
 * mockup anchors stay map fog. Empty copy stays fog (headers only).
 */
export function ProcessInstanceEventsTable({
  instanceId,
  tenantId = null,
  events: eventsOverride,
}: ProcessInstanceEventsTableProps) {
  const [events, setEvents] = useState<ProcessInstanceEventRow[]>(eventsOverride ?? []);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(eventsOverride === undefined);

  useEffect(() => {
    if (eventsOverride !== undefined) {
      setEvents(eventsOverride ?? []);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchProcessInstanceEvents(instanceId, tenantId)
      .then((payload) => {
        if (!cancelled) setEvents(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load events');
          setEvents([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [instanceId, tenantId, eventsOverride]);

  return (
    <Card variant="bordered" className="overflow-x-auto">
      <div
        className={cn(
          'grid gap-3.5 border-b border-border bg-muted/60 px-[22px] py-3',
          'text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
          GRID_MIN_WIDTH,
          GRID_COLS,
        )}
      >
        <div>ID</div>
        <div>Bpmn process</div>
        <div>Task name</div>
        <div>Task identifier</div>
        <div>Task type</div>
        <div>Event type</div>
        <div>User</div>
        <div>Timestamp</div>
      </div>

      {error ? (
        <p className="px-[22px] py-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="px-[22px] py-8 text-sm text-muted-foreground" aria-busy="true">
          Loading events…
        </p>
      ) : null}

      {!loading &&
        events.map((event) => (
          <div
            key={event.id}
            className={cn(
              'grid items-center gap-3.5 border-b border-border px-[22px] py-[13px]',
              GRID_MIN_WIDTH,
              GRID_COLS,
            )}
          >
            <div className="font-mono text-[13px] font-medium text-info">{event.id}</div>
            <div className="min-w-0 break-all font-mono text-[12px] text-muted-foreground">
              {cell(event.bpmn_process)}
            </div>
            <div className="text-[13px]">{cell(event.task_name)}</div>
            <div className="text-[13px] text-muted-foreground">{cell(event.task_identifier)}</div>
            <div className="text-[13px] text-muted-foreground">{cell(event.task_type)}</div>
            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-0.5 text-[12px] font-semibold text-success whitespace-nowrap">
                {event.event_type}
              </span>
            </div>
            <div className="text-[13px] text-muted-foreground italic">{event.user}</div>
            <time
              className="font-mono text-[12.5px] text-foreground"
              dateTime={event.timestamp != null ? new Date(event.timestamp * 1000).toISOString() : undefined}
            >
              {formatEventTimestamp(event.timestamp)}
            </time>
          </div>
        ))}
    </Card>
  );
}
