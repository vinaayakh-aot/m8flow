import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  fetchProcessInstanceCompletableTasks,
  type ProcessInstanceCompletableTaskRow,
} from '@/lib/processInstancesApi';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export type ProcessInstanceCompletableTasksTableProps = {
  instanceId: number;
  tenantId?: string | null;
  /** When set, skip the network fetch (page-shell prototype / tests). */
  tasks?: ProcessInstanceCompletableTaskRow[] | null;
};

const GRID_COLS = 'grid-cols-[minmax(160px,2fr)_minmax(0,140px)_minmax(0,100px)]';
const GRID_MIN_WIDTH = 'min-w-[520px]';

function taskLabel(task: ProcessInstanceCompletableTaskRow): string {
  const title = task.task_title?.trim();
  return title || task.task_name;
}

function waitingFor(task: ProcessInstanceCompletableTaskRow): string {
  const lane = task.lane_name?.trim();
  return lane || '—';
}

/**
 * Tasks I can complete — current-user candidate human tasks on this
 * instance. Go opens Task Review (`/task-review/{human_task_id}`). Empty
 * copy stays map fog (headers only).
 */
export function ProcessInstanceCompletableTasksTable({
  instanceId,
  tenantId = null,
  tasks: tasksOverride,
}: ProcessInstanceCompletableTasksTableProps) {
  const [tasks, setTasks] = useState<ProcessInstanceCompletableTaskRow[]>(tasksOverride ?? []);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(tasksOverride === undefined);

  useEffect(() => {
    if (tasksOverride !== undefined) {
      setTasks(tasksOverride ?? []);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchProcessInstanceCompletableTasks(instanceId, tenantId)
      .then((payload) => {
        if (!cancelled) setTasks(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load tasks');
          setTasks([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [instanceId, tenantId, tasksOverride]);

  return (
    <section>
      <h2 className="mb-3 font-display text-[19px] font-semibold text-foreground">
        Tasks I can complete
      </h2>
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
          <div>Waiting for</div>
          <div className="text-right">Actions</div>
        </div>

        {error ? (
          <p className="px-[22px] py-4 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="px-[22px] py-8 text-sm text-muted-foreground" aria-busy="true">
            Loading tasks…
          </p>
        ) : null}

        {!loading &&
          tasks.map((task) => (
            <div
              key={task.id}
              className={cn(
                'grid items-center gap-4 border-b border-border px-[22px] py-3.5',
                GRID_MIN_WIDTH,
                GRID_COLS,
              )}
            >
              <div className="text-[14.5px] font-semibold text-foreground">{taskLabel(task)}</div>
              <div className="text-[13.5px] text-muted-foreground">{waitingFor(task)}</div>
              <div className="flex justify-end">
                <Button asChild variant="pill-info" size="pill">
                  <Link to={`/task-review/${task.id}`}>Go</Link>
                </Button>
              </div>
            </div>
          ))}
      </Card>
    </section>
  );
}
