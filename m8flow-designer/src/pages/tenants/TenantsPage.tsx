import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { ArrowDown, ArrowUp, Building2, Plus, Search } from 'lucide-react';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  createTenant,
  fetchTenants,
  generateUniqueTenantAlias,
  isDuplicateTenantName,
  MAX_TENANT_NAME_LENGTH,
  tenantsErrorMessage,
  validateTenantDisplayName,
  type Tenant,
  type TenantStatus,
} from '@/lib/tenantsApi';
import { cn } from '@/lib/utils';

type SearchField = 'name' | 'slug';
type SortField = 'name' | 'slug';
type SortDirection = 'asc' | 'desc';
type StatusFilter = 'all' | 'ACTIVE' | 'INACTIVE';

const STATUS_BADGE: Record<TenantStatus, 'success' | 'warning' | 'destructive'> = {
  ACTIVE: 'success',
  INACTIVE: 'warning',
  DELETED: 'destructive',
};

const SELECT_CLASS =
  'appearance-none rounded-full border border-border bg-card px-3.5 py-2 pr-8 text-[13px] font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-nav-active/40';

/**
 * Super-admin tenant registry. List / search / sort / status filter / create.
 * Selecting a tenant opens tenant admin for that tenant.
 * Does not set `m8flow_selected_tenant`, mutate status, or delete.
 */
export default function TenantsPage() {
  const { isSuperAdmin, refreshTenants } = useOutletContext<AppShellOutletContext>();

  const [rows, setRows] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(isSuperAdmin);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchField, setSearchField] = useState<SearchField>('name');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const [createOpen, setCreateOpen] = useState(false);
  const [dialogName, setDialogName] = useState('');
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isSuperAdmin) {
      setRows([]);
      setLoading(false);
      setError(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchTenants()
      .then((payload) => {
        if (!cancelled) {
          setRows(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(tenantsErrorMessage(err, 'Failed to load tenants'));
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
  }, [isSuperAdmin, reloadKey]);

  const visible = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    let filtered = rows;
    if (query) {
      filtered = filtered.filter((tenant) =>
        searchField === 'name'
          ? tenant.name.toLowerCase().includes(query)
          : tenant.slug.toLowerCase().includes(query),
      );
    }
    if (statusFilter !== 'all') {
      filtered = filtered.filter((tenant) => tenant.status === statusFilter);
    }
    return [...filtered].sort((a, b) => {
      const left = a[sortField].toLowerCase();
      const right = b[sortField].toLowerCase();
      const compared = left.localeCompare(right);
      return sortDirection === 'asc' ? compared : -compared;
    });
  }, [rows, searchQuery, searchField, statusFilter, sortField, sortDirection]);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortField(field);
    setSortDirection('asc');
  }

  function openCreate() {
    setCreateOpen(true);
    setDialogName('');
    setDialogError(null);
  }

  function closeDialog() {
    if (saving) {
      return;
    }
    setCreateOpen(false);
    setDialogName('');
    setDialogError(null);
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    if (!createOpen || saving) {
      return;
    }
    const trimmed = dialogName.trim();
    const nameError = validateTenantDisplayName(trimmed);
    if (nameError) {
      setDialogError(nameError);
      return;
    }
    if (isDuplicateTenantName(trimmed, rows)) {
      setDialogError('A tenant with this name already exists.');
      return;
    }

    setSaving(true);
    setDialogError(null);
    try {
      await createTenant(trimmed, rows);
      setCreateOpen(false);
      setDialogName('');
      setReloadKey((key) => key + 1);
      refreshTenants?.();
    } catch (err: unknown) {
      setDialogError(tenantsErrorMessage(err, 'Failed to create tenant'));
    } finally {
      setSaving(false);
    }
  }

  if (!isSuperAdmin) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="font-display text-[32px] font-semibold tracking-tight">Tenants</h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Not available</p>
          <p className="mt-2 text-sm text-muted-foreground">
            The tenant registry is for platform admins. Your role cannot list or manage
            tenants.
          </p>
        </Card>
      </main>
    );
  }

  const searchPlaceholder =
    searchField === 'name' ? 'Search by tenant name' : 'Search by tenant alias';
  const emptyCopy =
    searchQuery.trim() || statusFilter !== 'all'
      ? 'No tenants found matching your filters'
      : 'No tenants available';

  return (
    <main className="flex-1 px-11 py-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[32px] font-semibold tracking-tight">Tenants</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Register the organizations that back access in Keycloak. Select a tenant
            to manage members, groups, roles, and invitations.
          </p>
        </div>
        <Button
          type="button"
          variant="pill-dark"
          size="pill"
          onClick={openCreate}
          data-testid="tenant-add-button"
        >
          <Plus className="size-3.5" aria-hidden />
          Add Tenant
        </Button>
      </div>

      <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
        <label className="relative">
          <span className="sr-only">Search by</span>
          <select
            className={SELECT_CLASS}
            value={searchField}
            onChange={(event) => setSearchField(event.target.value as SearchField)}
            data-testid="tenant-search-type-select"
          >
            <option value="name">Tenant name</option>
            <option value="slug">Tenant alias</option>
          </select>
        </label>
        <label className="flex min-w-0 flex-1 items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2.5">
          <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
          <Input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={searchPlaceholder}
            className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] text-foreground shadow-none outline-none focus-visible:ring-0"
            data-testid="tenant-search-input"
            aria-label={searchPlaceholder}
          />
        </label>
        <label className="relative">
          <span className="sr-only">Status</span>
          <select
            className={SELECT_CLASS}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
            data-testid="tenant-status-filter"
          >
            <option value="all">Any status</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </select>
        </label>
        <div className="ml-auto whitespace-nowrap text-[13px] text-muted-foreground">
          {loading
            ? 'Loading…'
            : `Showing ${visible.length} of ${rows.length} tenant${rows.length === 1 ? '' : 's'}`}
        </div>
      </div>

      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Card variant="bordered" className="overflow-hidden">
        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading tenants…</p>
        ) : visible.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">{emptyCopy}</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">
                  <SortHeader
                    label="Tenant name"
                    field="name"
                    active={sortField}
                    direction={sortDirection}
                    onToggle={toggleSort}
                  />
                </th>
                <th className="px-[22px] py-3 font-medium">
                  <SortHeader
                    label="Tenant alias"
                    field="slug"
                    active={sortField}
                    direction={sortDirection}
                    onToggle={toggleSort}
                  />
                </th>
                <th className="px-[22px] py-3 font-medium">Status</th>
                <th className="px-[22px] py-3 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((tenant) => {
                const managementPath = `/tenant-management/${encodeURIComponent(tenant.id)}`;
                return (
                  <tr
                    key={tenant.id}
                    className="border-b border-border last:border-b-0"
                    data-testid={`tenant-row-${tenant.id}`}
                  >
                    <td className="px-[22px] py-3 font-medium text-foreground">
                      <Link
                        to={managementPath}
                        state={{ tenantName: tenant.name }}
                        className="text-left font-medium text-foreground no-underline hover:underline"
                        data-testid={`tenant-open-${tenant.id}`}
                      >
                        {tenant.name}
                      </Link>
                    </td>
                    <td className="px-[22px] py-3 font-mono text-[13px] text-muted-foreground">
                      {tenant.slug}
                    </td>
                    <td className="px-[22px] py-3">
                      <Badge variant={STATUS_BADGE[tenant.status]}>{tenant.status}</Badge>
                    </td>
                    <td className="px-[22px] py-3 text-right whitespace-nowrap">
                      <Button variant="ghost" size="sm" asChild>
                        <Link
                          to={managementPath}
                          state={{ tenantName: tenant.name }}
                          data-testid={`tenant-manage-${tenant.id}`}
                        >
                          Manage
                        </Link>
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <Dialog open={createOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={(event) => void handleSave(event)}>
            <DialogHeader>
              <DialogTitle>Add Tenant</DialogTitle>
              <DialogDescription>
                Give this organization a display name. The alias is generated from it.
              </DialogDescription>
            </DialogHeader>
            <label className="mt-4 block text-sm font-medium text-foreground">
              Tenant name
              <Input
                className="mt-1.5"
                value={dialogName}
                onChange={(event) => setDialogName(event.target.value)}
                autoComplete="off"
                maxLength={MAX_TENANT_NAME_LENGTH}
                data-testid="tenant-name"
                required
              />
            </label>
            {dialogName.trim() ? (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                <Building2 className="size-3" aria-hidden />
                Alias: {generateUniqueTenantAlias(dialogName, rows)}
              </p>
            ) : null}
            {dialogError ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {dialogError}
              </p>
            ) : null}
            <DialogFooter className="mt-4">
              <Button type="button" variant="pill-cancel" size="pill" onClick={closeDialog}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="pill-dark"
                size="pill"
                disabled={!dialogName.trim() || saving}
                data-testid="tenant-save"
              >
                {saving ? 'Saving…' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function SortHeader({
  label,
  field,
  active,
  direction,
  onToggle,
}: {
  label: string;
  field: SortField;
  active: SortField;
  direction: SortDirection;
  onToggle: (field: SortField) => void;
}) {
  const isActive = active === field;
  const Icon = isActive && direction === 'desc' ? ArrowDown : ArrowUp;
  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center gap-1 tracking-[0.06em] uppercase',
        isActive ? 'text-foreground' : 'text-muted-foreground',
      )}
      onClick={() => onToggle(field)}
      aria-label={`Sort by ${label}, ${isActive ? direction : 'ascending'}`}
      data-testid={`tenant-sort-${field}`}
    >
      {label}
      <Icon className={cn('size-3', isActive ? 'opacity-100' : 'opacity-40')} aria-hidden />
    </button>
  );
}
