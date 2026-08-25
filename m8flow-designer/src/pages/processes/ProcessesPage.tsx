import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useOutletContext, useSearchParams } from 'react-router-dom';

import {
  ApiError,
  deleteProcessModel,
  fetchProcessGroups,
  fetchProcessModels,
  startProcessInstance,
  type ProcessGroupListItem,
  type ProcessModelListItem,
} from '@/lib/api';
import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { ProcessGroupsPicker } from './components/ProcessGroupsPicker';
import { ProcessesModelsList } from './components/ProcessesModelsList';
import { Card } from '@/components/ui/card';
import { encodeProcessModelId } from '@/lib/processModelId';

/** Turns a start-instance failure into a message the user can act on. The
 * backend returns 422 for an unstartable model (e.g. no start event), 403
 * when the caller lacks the start permission. */
function startErrorMessage(err: unknown, displayName: string): string {
  if (err instanceof ApiError) {
    // The backend's own reason is the most specific (e.g. a lane with no
    // owners, a missing start event) — show it verbatim when available.
    if (err.serverMessage) {
      return err.serverMessage;
    }
    if (err.status === 422) {
      return `“${displayName}” can’t be started — its diagram may be missing a start event.`;
    }
    if (err.status === 403) {
      return `You don’t have permission to start “${displayName}”.`;
    }
  }
  return err instanceof Error ? err.message : 'Failed to start process';
}

/**
 * Processes models list — wired to GET /v1.0/m8flow/process-models.
 * Super-admin must pick a concrete tenant (no All-Tenants catalog merge).
 */
export default function ProcessesPage() {
  const { scopedTenantId, isSuperAdmin, canManageProcesses } =
    useOutletContext<AppShellOutletContext>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const groupFilter = searchParams.get('group');
  const needsTenant = isSuperAdmin && !scopedTenantId;

  const [models, setModels] = useState<ProcessModelListItem[]>([]);
  const [loading, setLoading] = useState(!needsTenant);
  const [error, setError] = useState<string | null>(null);
  /** Unfiltered count for empty-state copy when a group filter is active. */
  const [allCount, setAllCount] = useState(0);

  const [groupsOpen, setGroupsOpen] = useState(false);
  const [groups, setGroups] = useState<ProcessGroupListItem[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupsError, setGroupsError] = useState<string | null>(null);
  /** Bumped after a successful delete to re-run the models fetch effect. */
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (needsTenant) {
      setModels([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const listPromise = fetchProcessModels(scopedTenantId, groupFilter);
    const allPromise = groupFilter
      ? fetchProcessModels(scopedTenantId, null)
      : listPromise;

    Promise.all([listPromise, allPromise])
      .then(([rows, allRows]) => {
        if (cancelled) {
          return;
        }
        setModels(rows);
        setAllCount(allRows.length);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load process models');
          setModels([]);
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
  }, [scopedTenantId, groupFilter, needsTenant, refreshKey]);

  useEffect(() => {
    if (!groupsOpen || needsTenant) {
      return;
    }

    let cancelled = false;
    setGroupsLoading(true);
    setGroupsError(null);

    fetchProcessGroups(scopedTenantId)
      .then((rows) => {
        if (!cancelled) {
          setGroups(rows);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setGroupsError(err instanceof Error ? err.message : 'Failed to load process groups');
          setGroups([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setGroupsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [groupsOpen, scopedTenantId, needsTenant]);

  const scopeLabel = useMemo(() => {
    if (!groupFilter) {
      return 'All groups';
    }
    const fromGroups = groups.find((g) => g.id === groupFilter);
    if (fromGroups) {
      return fromGroups.display_name || groupFilter;
    }
    const match = models.find((m) => m.group_id === groupFilter);
    return match?.group_display_name || groupFilter;
  }, [groupFilter, models, groups]);

  function setGroup(groupId: string | null) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (groupId) {
          next.set('group', groupId);
        } else {
          next.delete('group');
        }
        return next;
      },
      { replace: true },
    );
  }

  const closeGroups = useCallback(() => setGroupsOpen(false), []);

  async function handleStartModel(model: ProcessModelListItem) {
    setError(null);
    try {
      const result = await startProcessInstance(encodeProcessModelId(model.id), scopedTenantId);
      navigate(`/process-instances/${result.id}`);
    } catch (err: unknown) {
      setError(startErrorMessage(err, model.display_name));
    }
  }

  // Rethrows so ProcessesModelsList's confirmation dialog can surface the
  // failure (notably the 409 when the model still has instances); only the
  // success path refreshes the list.
  async function handleDeleteModel(model: ProcessModelListItem) {
    await deleteProcessModel(encodeProcessModelId(model.id), scopedTenantId);
    setRefreshKey((k) => k + 1);
  }

  if (needsTenant) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="text-[32px] font-semibold tracking-tight">Processes</h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Choose a tenant</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Process models are tenant-scoped. Select a concrete tenant in the sidebar
            — All Tenants is not supported on Processes.
          </p>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex-1 px-11 py-10">
      <ProcessesModelsList
        models={models}
        loading={loading}
        error={error}
        groupFilter={groupFilter}
        scopeLabel={scopeLabel}
        totalUnfilteredCount={allCount}
        onBrowseGroups={() => setGroupsOpen(true)}
        onClearGroupFilter={() => setGroup(null)}
        onFilterByGroup={(groupId) => setGroup(groupId)}
        onOpenModel={(model) => {
          navigate(`/processes/${encodeProcessModelId(model.id)}`);
        }}
        onStartModel={canManageProcesses ? handleStartModel : undefined}
        onDeleteModel={canManageProcesses ? handleDeleteModel : undefined}
      />
      <ProcessGroupsPicker
        open={groupsOpen}
        groups={groups}
        loading={groupsLoading}
        error={groupsError}
        selectedGroupId={groupFilter}
        onClose={closeGroups}
        onSelectAll={() => {
          setGroup(null);
          setGroupsOpen(false);
        }}
        onSelectGroup={(groupId) => {
          setGroup(groupId);
          setGroupsOpen(false);
        }}
      />
    </main>
  );
}
