import { useEffect, useState } from 'react';

import { fetchHomeMyTasks, type HomeMyTask } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { formatRelativeTimeVerbose } from '@/lib/relativeTime';

export type MyTasksListProps = {
  tenantId?: string | null;
  /** When set, skip the network fetch (prototype / tests). */
  tasks?: HomeMyTask[] | null;
};

function taskTitle(task: HomeMyTask): string {
  return task.task_title?.trim() || task.task_name;
}

function waitingOn(task: HomeMyTask): string {
  return task.lane_name?.trim() || '—';
}

/**
 * Home "My tasks" list — title, "tenant · waiting on lane", verbose relative
 * created time. "View all" is inert (no tasks inbox route in this map).
 */
export function MyTasksList({ tenantId = null, tasks: tasksOverride }: MyTasksListProps) {
  const [tasks, setTasks] = useState<HomeMyTask[]>(tasksOverride ?? []);
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
    fetchHomeMyTasks(tenantId)
      .then((payload) => {
        if (!cancelled) {
          setTasks(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load tasks');
          setTasks([]);
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
  }, [tenantId, tasksOverride]);

  return (
    <Card variant="bordered" className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-[22px] py-[18px]">
        <h2 className="text-[15px] font-semibold text-foreground">My tasks</h2>
        <span
          aria-disabled="true"
          className="cursor-default text-[13px] font-semibold text-info select-none"
        >
          View all
        </span>
      </div>

      {error ? (
        <p className="px-[22px] py-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div aria-busy={loading}>
        {loading ? (
          <div className="border-t border-border px-[22px] py-4 text-sm text-muted-foreground">
            Loading…
          </div>
        ) : null}

        {!loading && tasks.length === 0 && !error ? (
          <div className="border-t border-border px-[22px] py-4 text-sm text-muted-foreground">
            No pending tasks.
          </div>
        ) : null}

        {tasks.map((task) => (
          <div key={task.id} className="border-t border-border px-[22px] py-3.5">
            <div className="mb-1 text-[13.5px] font-semibold text-foreground">
              {taskTitle(task)}
            </div>
            <div className="text-[12.5px] text-muted-foreground">
              {task.tenant_name} · waiting on {waitingOn(task)}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground/80">
              {formatRelativeTimeVerbose(task.created_at_in_seconds)}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
