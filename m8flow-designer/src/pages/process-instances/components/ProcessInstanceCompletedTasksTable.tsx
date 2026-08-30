import { useEffect, useState } from 'react';

import {
  fetchProcessInstanceCompletedTasks,
  type ProcessInstanceCompletedTaskRow,
  type ProcessInstanceCompletedTasksResponse,
} from '@/lib/processInstancesApi';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export type ProcessInstanceCompletedTasksTableProps = {
  instanceId: number;
  tenantId?: string | null;
  /** When set, skip the network fetch (page-shell prototype / tests). */
  data?: ProcessInstanceCompletedTasksResponse | null;
};

const GRID_COLS = 'grid-cols-[minmax(160px,2fr)_minmax(0,140px)_minmax(0,160px)]';
const GRID_MIN_WIDTH = 'min-w-[560px]';

type SubTab = 'completedByMe' | 'allCompleted';

function taskLabel(task: ProcessInstanceCompletedTaskRow): string {
  const title = task.task_title?.trim();
  return title || task.task_name;
}

function completedBy(task: ProcessInstanceCompletedTaskRow): string {
  const name = task.completed_by?.trim();
  return name || '—';
}

/** UTC `YYYY-MM-DD HH:MM:SS` matching Events; not a link. */
function formatTimestamp(epochSeconds: number | null | undefined): string {
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

const EMPTY: ProcessInstanceCompletedTasksResponse = {
  completed_by_me: [],
  all_completed: [],
};

/**
 * Tasks tab body for process instance detail: Completed by me / All
 * completed. Fetches GET /v1.0/m8flow/process-instances/{id}/completed-tasks.
 * Task is title else name, never owner. Empty "Completed by me" uses the
 * mockup sentence. All-completed empty copy stays fog (headers only).
 */
export function ProcessInstanceCompletedTasksTable({
  instanceId,
  tenantId = null,
  data: dataOverride,
}: ProcessInstanceCompletedTasksTableProps) {
  const [data, setData] = useState<ProcessInstanceCompletedTasksResponse>(dataOverride ?? EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(dataOverride === undefined);
  const [subTab, setSubTab] = useState<SubTab>('completedByMe');

  useEffect(() => {
    if (dataOverride !== undefined) {
      setData(dataOverride ?? EMPTY);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchProcessInstanceCompletedTasks(instanceId, tenantId)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load tasks');
          setData(EMPTY);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [instanceId, tenantId, dataOverride]);

  const rows = subTab === 'completedByMe' ? data.completed_by_me : data.all_completed;
  const showMineEmpty = !loading && !error && subTab === 'completedByMe' && rows.length === 0;

  return (
    <section>
      <div className="mb-4 flex items-center gap-[22px]">
        <button
          type="button"
          aria-pressed={subTab === 'completedByMe'}
          onClick={() => setSubTab('completedByMe')}
          className={cn(
            'cursor-pointer border-x-0 border-t-0 border-b-2 bg-transparent py-2.5 font-sans text-[14.5px]',
            subTab === 'completedByMe'
              ? 'border-info font-semibold text-info'
              : 'border-transparent font-medium text-muted-foreground',
          )}
        >
          Completed by me
        </button>
        <button
          type="button"
          aria-pressed={subTab === 'allCompleted'}
          onClick={() => setSubTab('allCompleted')}
          className={cn(
            'cursor-pointer border-x-0 border-t-0 border-b-2 bg-transparent py-2.5 font-sans text-[14.5px]',
            subTab === 'allCompleted'
              ? 'border-info font-semibold text-info'
              : 'border-transparent font-medium text-muted-foreground',
          )}
        >
          All completed
        </button>
      </div>

      {error ? (
        <p className="py-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="py-8 text-sm text-muted-foreground" aria-busy="true">
          Loading tasks…
        </p>
      ) : null}

      {showMineEmpty ? (
        <p className="m-0 text-[13.5px] text-muted-foreground italic">
          You have not completed any tasks for this process instance.
        </p>
      ) : null}

      {!loading && !showMineEmpty ? (
        <Card variant="bordered" className="overflow-x-auto">
          <div
            className={cn(
              'grid gap-4 border-b border-border bg-muted/60 px-[22px] py-3',
              'text-[11px] tracking-[0.05em] text-muted-foreground uppercase',
              GRID_MIN_WIDTH,
              GRID_COLS,
            )}
          >
            <div>Task</div>
            <div>Completed by</div>
            <div>Timestamp</div>
          </div>

          {rows.map((task) => (
            <div
              key={task.id}
              className={cn(
                'grid items-center gap-4 border-t border-border px-[22px] py-[13px]',
                GRID_MIN_WIDTH,
                GRID_COLS,
              )}
            >
              <div className="text-[14px] text-foreground">{taskLabel(task)}</div>
              <div className="text-[13px] text-muted-foreground">{completedBy(task)}</div>
              <time
                className="font-mono text-[12.5px] text-muted-foreground"
                dateTime={
                  task.timestamp != null ? new Date(task.timestamp * 1000).toISOString() : undefined
                }
              >
                {formatTimestamp(task.timestamp)}
              </time>
            </div>
          ))}
        </Card>
      ) : null}
    </section>
  );
}
