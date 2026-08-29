import { FormEvent, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Copy, KeyRound } from 'lucide-react';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
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
  authenticationsErrorMessage,
  createAuthentication,
  fetchAuthentications,
  revokeAuthentication,
  type CreatedServiceAccount,
  type ServiceAccount,
} from '@/lib/authenticationsApi';
import { formatRelativeTime } from '@/lib/relativeTime';

/**
 * Tenant-scoped service accounts (Identity + Auth map, ticket 05).
 * Setup → Authentications — not Configuration, not members admin.
 */
export default function AuthenticationsPage() {
  const {
    scopedTenantId,
    isSuperAdmin,
    canReadAuthentications = false,
    canManageAuthentications = false,
  } = useOutletContext<AppShellOutletContext>();
  const needsTenant = isSuperAdmin && !scopedTenantId;

  const [rows, setRows] = useState<ServiceAccount[]>([]);
  const [loading, setLoading] = useState(canReadAuthentications && !needsTenant);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [minted, setMinted] = useState<CreatedServiceAccount | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!canReadAuthentications || needsTenant) {
      setRows([]);
      setLoading(false);
      setError(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAuthentications(scopedTenantId)
      .then((payload) => {
        if (!cancelled) {
          setRows(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(authenticationsErrorMessage(err, 'Failed to load authentications'));
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
  }, [canReadAuthentications, needsTenant, scopedTenantId, reloadKey]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    const cleaned = name.trim();
    if (!cleaned || creating) {
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createAuthentication(cleaned, scopedTenantId);
      setMinted(created);
      setCopied(false);
      setName('');
      setCreateOpen(false);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setCreateError(authenticationsErrorMessage(err, 'Failed to create service account'));
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(row: ServiceAccount) {
    if (!window.confirm(`Revoke “${row.name}”? API calls with this key will stop working.`)) {
      return;
    }
    setError(null);
    try {
      await revokeAuthentication(row.id, scopedTenantId);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setError(authenticationsErrorMessage(err, 'Failed to revoke service account'));
    }
  }

  async function copyKey() {
    if (!minted?.api_key) {
      return;
    }
    try {
      await navigator.clipboard.writeText(minted.api_key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  if (!canReadAuthentications) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="font-display text-[32px] font-semibold tracking-tight">Authentications</h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Not available</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Service accounts are for integrators and tenant admins. Your role cannot
            list or manage them.
          </p>
        </Card>
      </main>
    );
  }

  if (needsTenant) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="font-display text-[32px] font-semibold tracking-tight">Authentications</h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Choose a tenant</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Service accounts are tenant-scoped. Select a concrete tenant in the sidebar —
            All Tenants is not supported here.
          </p>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex-1 px-11 py-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[32px] font-semibold tracking-tight">Authentications</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Tenant-scoped API keys for machine access. The secret is shown once when you
            create a key.
          </p>
        </div>
        {canManageAuthentications ? (
          <Button
            type="button"
            variant="pill-dark"
            size="pill"
            onClick={() => {
              setCreateError(null);
              setCreateOpen(true);
            }}
          >
            <KeyRound className="size-3.5" aria-hidden />
            New service account
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Card variant="bordered" className="overflow-hidden">
        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading authentications…</p>
        ) : rows.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">
            No service accounts in this tenant yet.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">Name</th>
                <th className="px-[22px] py-3 font-medium">Client id</th>
                <th className="px-[22px] py-3 font-medium">Created</th>
                {canManageAuthentications ? (
                  <th className="px-[22px] py-3 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-border last:border-b-0">
                  <td className="px-[22px] py-3 font-medium text-foreground">{row.name}</td>
                  <td className="px-[22px] py-3 font-mono text-[13px] text-muted-foreground">
                    {row.client_id}
                  </td>
                  <td className="px-[22px] py-3 text-muted-foreground">
                    {formatRelativeTime(row.created_at_in_seconds)}
                  </td>
                  {canManageAuthentications ? (
                    <td className="px-[22px] py-3 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleRevoke(row)}
                      >
                        Revoke
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={(event) => void handleCreate(event)}>
            <DialogHeader>
              <DialogTitle>New service account</DialogTitle>
              <DialogDescription>
                Give this key a name you will recognize later. The secret is shown only
                once after you create it.
              </DialogDescription>
            </DialogHeader>
            <label className="mt-4 block text-sm font-medium text-foreground">
              Name
              <Input
                className="mt-1.5"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="off"
                data-testid="authentication-name"
                required
              />
            </label>
            {createError ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {createError}
              </p>
            ) : null}
            <DialogFooter className="mt-4">
              <Button type="button" variant="pill-cancel" size="pill" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="pill-dark"
                size="pill"
                disabled={!name.trim() || creating}
                data-testid="authentication-create"
              >
                {creating ? 'Creating…' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(minted)} onOpenChange={(open) => !open && setMinted(null)}>
        <DialogContent className="sm:max-w-lg" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Copy this key now</DialogTitle>
            <DialogDescription>
              This is the only time the secret is shown. Store it with your integrator —
              we only keep a hash.
            </DialogDescription>
          </DialogHeader>
          {minted ? (
            <div className="mt-3 rounded-lg border border-border bg-muted/40 px-3 py-2">
              <div className="text-[11px] tracking-wide text-muted-foreground uppercase">
                {minted.name}
              </div>
              <code
                className="mt-1 block break-all font-mono text-[13px] text-foreground"
                data-testid="authentication-api-key"
              >
                {minted.api_key}
              </code>
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="pill-outline" size="pill" onClick={() => void copyKey()}>
              <Copy className="size-3.5" aria-hidden />
              {copied ? 'Copied' : 'Copy key'}
            </Button>
            <Button
              type="button"
              variant="pill-dark"
              size="pill"
              onClick={() => setMinted(null)}
              data-testid="authentication-secret-done"
            >
              I have copied it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
