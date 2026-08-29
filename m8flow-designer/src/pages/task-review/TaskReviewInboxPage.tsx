import { useEffect, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/card';
import { StatusBadge } from '@/components/StatusBadge';
import { formatRelativeTime } from '@/lib/relativeTime';
import {
  fetchTaskReviewList,
  type TaskReviewListItem,
  type TaskReviewPagination,
} from '@/lib/tasksApi';

const PER_PAGE = 20;

/**
 * Task Review — "My tasks" inbox. Wired to GET /v1.0/m8flow/task-review
 * (the caller's pending human tasks; super-admin sees every tenant's,
 * narrowable via the sidebar tenant selector). Rows open the review detail
 * at `/task-review/:taskId`. Same outlet-context tenant-scoping + fetch
 * state-machine as ProcessInstancesPage; super-admin is NOT forced to pick a
 * concrete tenant here (the backend returns all-tenant pending tasks).
 */
export default function TaskReviewInboxPage() {
  const { scopedTenantId, isSuperAdmin } = useOutletContext<AppShellOutletContext>();
  const navigate = useNavigate();

  const [tasks, setTasks] = useState<TaskReviewListItem[]>([]);
  const [pagination, setPagination] = useState<TaskReviewPagination | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTaskReviewList({ page, perPage: PER_PAGE, tenantId: scopedTenantId ?? undefined })
      .then(({ results, pagination: pg }) => {
        if (!cancelled) {
          setTasks(results);
          setPagination(pg);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load tasks');
          setTasks([]);
          setPagination(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [scopedTenantId, page]);

  const total = pagination?.total ?? tasks.length;
  const pageCount = Math.max(Math.ceil(total / PER_PAGE), 1);

  return (
    <main className="flex-1 px-11 py-10">
      <div className="mb-7">
        <h1 className="font-display text-[32px] font-semibold tracking-tight">Task Review</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pending tasks awaiting your review.
        </p>
      </div>

      <Card variant="bordered" className="overflow-hidden">
        <div aria-busy={loading}>
          {error ? (
            <p className="px-6 py-4 text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          {loading ? (
            <p className="px-6 py-6 text-sm text-muted-foreground">Loading…</p>
          ) : null}

          {!loading && !error && tasks.length === 0 ? (
            <p className="px-6 py-6 text-sm text-muted-foreground">No pending tasks.</p>
          ) : null}

          {!loading && !error && tasks.length > 0 ? (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  <th className="px-6 py-3">Task</th>
                  <th className="px-6 py-3">Process</th>
                  <th className="px-6 py-3">Submitted by</th>
                  {isSuperAdmin ? <th className="px-6 py-3">Tenant</th> : null}
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr
                    key={task.id}
                    onClick={() => navigate(`/task-review/${task.id}`)}
                    className="cursor-pointer border-b border-border last:border-0 hover:bg-muted/50"
                  >
                    <td className="px-6 py-3.5 font-medium text-foreground">
                      {task.task_title || task.task_name}
                    </td>
                    <td className="px-6 py-3.5 text-muted-foreground">
                      {task.process_model_display_name}
                    </td>
                    <td className="px-6 py-3.5 text-muted-foreground">
                      {task.submitted_by ?? '—'}
                    </td>
                    {isSuperAdmin ? (
                      <td className="px-6 py-3.5 text-muted-foreground">{task.tenant_name ?? '—'}</td>
                    ) : null}
                    <td className="px-6 py-3.5">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-6 py-3.5 text-muted-foreground">
                      {task.created_at_in_seconds != null
                        ? formatRelativeTime(task.created_at_in_seconds)
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      </Card>

      {!loading && !error && total > 0 ? (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {total} task{total === 1 ? '' : 's'}
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page <= 1}
              className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              Page {page} of {pageCount}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(p + 1, pageCount))}
              disabled={page >= pageCount}
              className="rounded-md border border-border px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </main>
  );
}
