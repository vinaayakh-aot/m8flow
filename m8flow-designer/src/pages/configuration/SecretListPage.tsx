import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  deleteSecret,
  fetchSecrets,
  secretsErrorMessage,
  type Secret,
  type SecretPagination,
} from '@/lib/secretsApi';

import { ConfigurationGate, useConfigurationContext } from './ConfigurationGate';

const PER_PAGE = 10;
const TITLE = 'Configuration';

export default function SecretListPage() {
  return (
    <ConfigurationGate title={TITLE}>
      <SecretListBody />
    </ConfigurationGate>
  );
}

function SecretListBody() {
  const { scopedTenantId, isSuperAdmin, canManageSecrets } = useConfigurationContext();
  const [rows, setRows] = useState<Secret[]>([]);
  const [pagination, setPagination] = useState<SecretPagination | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSecrets({ page, perPage: PER_PAGE, tenantId: scopedTenantId })
      .then((payload) => {
        if (!cancelled) {
          setRows(payload.results);
          setPagination(payload.pagination);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(secretsErrorMessage(err, 'Could not list secrets.'));
          setRows([]);
          setPagination(null);
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
  }, [page, scopedTenantId, reloadKey]);

  async function handleDelete(row: Secret) {
    if (!window.confirm(`Delete secret “${row.key}”? This cannot be undone.`)) {
      return;
    }
    setError(null);
    try {
      await deleteSecret(row.key, scopedTenantId);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setError(secretsErrorMessage(err, 'Could not delete secret.'));
    }
  }

  const pageCount = pagination ? Math.max(pagination.pages, 1) : 1;

  return (
    <main className="flex-1 px-11 py-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[32px] font-semibold tracking-tight">{TITLE}</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Tenant-scoped named credentials. After create, the value is never shown again.
          </p>
        </div>
        {canManageSecrets ? (
          <Button asChild variant="pill-dark" size="pill">
            <Link to="/configuration/secrets/new">
              <Plus className="size-3.5" aria-hidden />
              Add a secret
            </Link>
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert" data-testid="secret-list-error">
          {error}
        </p>
      ) : null}

      <Card variant="bordered" className="overflow-hidden">
        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading secrets…</p>
        ) : rows.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">
            No secrets in this tenant yet.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">Key</th>
                <th className="px-[22px] py-3 font-medium">Created by</th>
                {isSuperAdmin ? (
                  <th className="px-[22px] py-3 font-medium">Tenant</th>
                ) : null}
                {canManageSecrets ? (
                  <th className="px-[22px] py-3 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-b border-border last:border-b-0">
                  <td className="px-[22px] py-3 font-medium text-foreground">
                    <Link
                      className="text-foreground underline-offset-4 hover:underline"
                      to={`/configuration/secrets/${encodeURIComponent(row.key)}`}
                    >
                      {row.key}
                    </Link>
                  </td>
                  <td className="px-[22px] py-3 text-muted-foreground">{row.username || '—'}</td>
                  {isSuperAdmin ? (
                    <td
                      className="px-[22px] py-3 text-muted-foreground"
                      data-testid="secret-list-tenant-cell"
                    >
                      {row.tenantName || row.tenantId || '—'}
                    </td>
                  ) : null}
                  {canManageSecrets ? (
                    <td className="px-[22px] py-3 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleDelete(row)}
                      >
                        Delete
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {pagination && pagination.pages > 1 ? (
          <div className="flex items-center justify-end gap-2 border-t border-border px-[22px] py-3 text-sm text-muted-foreground">
            <button
              type="button"
              onClick={() => setPage((current) => Math.max(current - 1, 1))}
              disabled={page <= 1}
              aria-label="Previous page"
              className="flex size-7 items-center justify-center rounded-full border border-border disabled:opacity-40"
            >
              <ChevronLeft className="size-3.5" />
            </button>
            <span className="font-mono">
              Page {page} of {pageCount}
            </span>
            <button
              type="button"
              onClick={() => setPage((current) => Math.min(current + 1, pageCount))}
              disabled={page >= pageCount}
              aria-label="Next page"
              className="flex size-7 items-center justify-center rounded-full border border-border disabled:opacity-40"
            >
              <ChevronRight className="size-3.5" />
            </button>
          </div>
        ) : null}
      </Card>
    </main>
  );
}
