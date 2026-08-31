import { useEffect, useState } from 'react';
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom';

import { ApiError, copyProcessModel, createProcessModelFile, createScriptUnitTest, deleteProcessModelFile, fetchProcessModelDetail, fetchScriptUnitTests, runProcessModelTests, runScriptUnitTest, startProcessInstance, updateProcessModel, type ProcessModelDetail } from '@/lib/api';
import { ProcessModelOverview } from './components/ProcessModelOverview';
import { Card } from '@/components/ui/card';
import type { AppShellOutletContext } from '@/components/layout/AppShell';

/**
 * Process-model overview. Fetches GET /v1.0/m8flow/process-models/{id}
 * and renders the mockup layout. Route ids use `:` for `/`.
 */
export default function ProcessModelDetailPage() {
  const { processModelId } = useParams<{ processModelId: string }>();
  const { scopedTenantId, isSuperAdmin, canManageProcesses } =
    useOutletContext<AppShellOutletContext>();
  const canManageCatalog = Boolean(canManageProcesses) && !isSuperAdmin;
  const canStart = Boolean(canManageProcesses);
  const navigate = useNavigate();
  const needsTenant = isSuperAdmin && !scopedTenantId;
  const modifiedId = processModelId ?? '';

  const [detail, setDetail] = useState<ProcessModelDetail | null>(null);
  const [loading, setLoading] = useState(!needsTenant && Boolean(modifiedId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (needsTenant || !modifiedId) {
      setDetail(null);
      setLoading(false);
      setNotFound(!modifiedId && !needsTenant);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setError(null);

    fetchProcessModelDetail(modifiedId, scopedTenantId)
      .then((payload) => {
        if (!cancelled) {
          setDetail(payload);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setDetail(null);
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
          setError(null);
          return;
        }
        setNotFound(false);
        setError(err instanceof Error ? err.message : 'Failed to load process model');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [modifiedId, scopedTenantId, needsTenant]);

  if (needsTenant) {
    return (
      <main className="flex-1 px-11 py-10">
        <ShellHeader />
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

  if (loading) {
    return (
      <main className="flex-1 px-11 py-10">
        <ShellHeader />
        <p className="text-sm text-muted-foreground" aria-busy="true">
          Loading process model…
        </p>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="flex-1 px-11 py-10">
        <ShellHeader />
        <p className="text-sm text-muted-foreground" role="status">
          Process model not found.
        </p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex-1 px-11 py-10">
        <ShellHeader />
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      </main>
    );
  }

  if (!detail) {
    return null;
  }

  return (
    <main className="flex-1 px-11 py-10 pb-14">
      <ProcessModelOverview
        detail={detail}
        tenantId={scopedTenantId}
        canManage={canManageCatalog}
        onUpdateIdentity={
          canManageCatalog
            ? async (patch) => {
                const identity = await updateProcessModel(modifiedId, patch, scopedTenantId);
                setDetail((prev) => (prev ? { ...prev, ...identity } : prev));
              }
            : undefined
        }
        onAddFile={
          canManageCatalog
            ? async (input) => {
                await createProcessModelFile(modifiedId, input, scopedTenantId);
                setDetail(await fetchProcessModelDetail(modifiedId, scopedTenantId));
              }
            : undefined
        }
        onDeleteFile={
          canManageCatalog
            ? async (fileName) => {
                await deleteProcessModelFile(modifiedId, fileName, scopedTenantId);
                setDetail(await fetchProcessModelDetail(modifiedId, scopedTenantId));
              }
            : undefined
        }
        onSetPrimary={
          canManageCatalog
            ? async (fileName) => {
                await updateProcessModel(
                  modifiedId,
                  { primary_file_name: fileName },
                  scopedTenantId,
                );
                setDetail(await fetchProcessModelDetail(modifiedId, scopedTenantId));
              }
            : undefined
        }
        onStart={
          canStart
            ? async () => {
                const result = await startProcessInstance(modifiedId, scopedTenantId);
                navigate(`/process-instances/${result.id}`);
              }
            : undefined
        }
        onCopy={
          canManageCatalog
            ? async (input) => {
                const identity = await copyProcessModel(modifiedId, input, scopedTenantId);
                navigate(`/processes/${identity.id.split('/').join(':')}`);
                return identity;
              }
            : undefined
        }
        onSaveAsTemplate={
          canManageCatalog
            ? (templateId) => {
                navigate(`/templates/${templateId}`);
              }
            : undefined
        }
        onRunBpmnTests={
          canManageCatalog
            ? () => runProcessModelTests(modifiedId, scopedTenantId)
            : undefined
        }
        onFetchScriptUnitTests={
          canManageCatalog
            ? () => fetchScriptUnitTests(modifiedId, scopedTenantId)
            : undefined
        }
        onCreateScriptUnitTest={
          canManageCatalog
            ? (input) => createScriptUnitTest(modifiedId, input, scopedTenantId)
            : undefined
        }
        onRunScriptUnitTest={
          canManageCatalog
            ? (input) => runScriptUnitTest(modifiedId, input, scopedTenantId)
            : undefined
        }
      />
    </main>
  );
}

function ShellHeader() {
  return (
    <div className="mb-7">
      <Link
        to="/processes"
        className="mb-1.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-foreground no-underline"
      >
        ← All processes
      </Link>
      <h1 className="font-display text-[32px] font-semibold tracking-tight">Process model</h1>
    </div>
  );
}
