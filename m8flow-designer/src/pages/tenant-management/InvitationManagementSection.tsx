import { FormEvent, useEffect, useMemo, useState } from 'react';
import { MailPlus, RotateCw, Trash2 } from 'lucide-react';

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
  createTenantInvitation,
  fetchTenantInvitations,
  invitationManagementErrorMessage,
  resendTenantInvitation,
  revokeTenantInvitation,
  type TenantInvitation,
} from '@/lib/invitationManagementApi';
import { TENANT_ROLES, type TenantRole } from '@/lib/tenantAdminApi';

const INVITATIONS_PAGE_SIZE = 100;
const VALIDITY_OPTIONS = [1, 7, 30] as const;
const EMAIL_PATTERN = /\S+@\S+\.\S+/;

type InvitationManagementSectionProps = {
  tenantId: string;
  inviteOpen: boolean;
  onInviteOpenChange: (open: boolean) => void;
};

function statusVariant(
  status: TenantInvitation['status'],
): 'warning' | 'success' | 'outline' | 'destructive' {
  if (status === 'PENDING') {
    return 'warning';
  }
  if (status === 'ACCEPTED') {
    return 'success';
  }
  if (status === 'EXPIRED') {
    return 'destructive';
  }
  return 'outline';
}

function formatExpiry(seconds: number): string {
  try {
    return new Date(seconds * 1000).toLocaleString();
  } catch {
    return String(seconds);
  }
}

export default function InvitationManagementSection({
  tenantId,
  inviteOpen,
  onInviteOpenChange,
}: InvitationManagementSectionProps) {
  const [invitations, setInvitations] = useState<TenantInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [selectedRoles, setSelectedRoles] = useState<TenantRole[]>([]);
  const [validityDays, setValidityDays] = useState<(typeof VALIDITY_OPTIONS)[number]>(7);
  const [sending, setSending] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchTenantInvitations(tenantId, { limit: INVITATIONS_PAGE_SIZE })
      .then((payload) => {
        if (!cancelled) {
          setInvitations(payload.results);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(invitationManagementErrorMessage(err, 'Failed to load invitations'));
          setInvitations([]);
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
  }, [tenantId, reloadKey]);

  const canSubmit = useMemo(
    () => EMAIL_PATTERN.test(email.trim()) && selectedRoles.length > 0 && !sending,
    [email, selectedRoles, sending],
  );

  function resetInviteForm() {
    setEmail('');
    setSelectedRoles([]);
    setValidityDays(7);
    setInviteError(null);
    setDevLink(null);
    setSending(false);
  }

  function closeInvite() {
    if (sending) {
      return;
    }
    resetInviteForm();
    onInviteOpenChange(false);
  }

  function toggleRole(role: TenantRole) {
    setSelectedRoles((current) =>
      current.includes(role) ? current.filter((item) => item !== role) : [...current, role],
    );
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setSending(true);
    setInviteError(null);
    setDevLink(null);
    try {
      const payload = await createTenantInvitation(tenantId, {
        email: email.trim(),
        roles: selectedRoles,
        validity_days: validityDays,
      });
      setReloadKey((key) => key + 1);
      if (payload.invitation.invitation_link) {
        setDevLink(payload.invitation.invitation_link);
        setSending(false);
        return;
      }
      resetInviteForm();
      onInviteOpenChange(false);
    } catch (err: unknown) {
      setInviteError(invitationManagementErrorMessage(err, 'Failed to send invitation'));
      setSending(false);
    }
  }

  async function handleResend(invitation: TenantInvitation) {
    setMutatingId(invitation.id);
    setError(null);
    try {
      await resendTenantInvitation(tenantId, invitation.id);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setError(invitationManagementErrorMessage(err, 'Failed to resend invitation'));
    } finally {
      setMutatingId(null);
    }
  }

  async function handleRevoke(invitation: TenantInvitation) {
    setMutatingId(invitation.id);
    setError(null);
    try {
      await revokeTenantInvitation(tenantId, invitation.id);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setError(invitationManagementErrorMessage(err, 'Failed to revoke invitation'));
    } finally {
      setMutatingId(null);
    }
  }

  return (
    <>
      <Card variant="bordered" className="mt-6 overflow-hidden" data-testid="pending-invitations-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-[22px] py-3">
          <h2 className="text-[15px] font-semibold text-foreground">Invitations</h2>
        </div>

        {error ? (
          <p className="px-[22px] pt-4 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading invitations…</p>
        ) : invitations.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">No invitations yet.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">Email</th>
                <th className="px-[22px] py-3 font-medium">Roles</th>
                <th className="px-[22px] py-3 font-medium">Status</th>
                <th className="px-[22px] py-3 font-medium">Expires</th>
                <th className="px-[22px] py-3 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {invitations.map((invitation) => {
                const isPending = invitation.status === 'PENDING';
                const canResend =
                  invitation.status === 'PENDING' || invitation.status === 'EXPIRED';
                const isMutating = mutatingId === invitation.id;
                return (
                  <tr key={invitation.id} className="border-b border-border last:border-b-0">
                    <td className="px-[22px] py-3">{invitation.email}</td>
                    <td className="px-[22px] py-3">
                      <div className="flex flex-wrap gap-1">
                        {invitation.roles.map((role) => (
                          <Badge key={role} variant="outline">
                            {role}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-[22px] py-3">
                      <Badge variant={statusVariant(invitation.status)}>{invitation.status}</Badge>
                    </td>
                    <td className="px-[22px] py-3 text-muted-foreground">
                      {formatExpiry(invitation.expires_at_in_seconds)}
                    </td>
                    <td className="px-[22px] py-3 text-right whitespace-nowrap">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={!canResend || isMutating}
                        onClick={() => void handleResend(invitation)}
                        data-testid={`invitation-resend-${invitation.id}`}
                      >
                        <RotateCw className="size-3.5" aria-hidden />
                        Resend
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={!isPending || isMutating}
                        onClick={() => void handleRevoke(invitation)}
                        data-testid={`invitation-revoke-${invitation.id}`}
                      >
                        <Trash2 className="size-3.5" aria-hidden />
                        Revoke
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <Dialog
        open={inviteOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeInvite();
          } else {
            onInviteOpenChange(true);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          {devLink ? (
            <>
              <DialogHeader>
                <DialogTitle>Invitation created</DialogTitle>
                <DialogDescription>
                  Email is not configured, so share this single-use link. It uses the Accept
                  invitation path, not this admin panel.
                </DialogDescription>
              </DialogHeader>
              <Input className="mt-4" value={devLink} readOnly />
              <DialogFooter className="mt-4">
                <Button type="button" variant="pill-dark" size="pill" onClick={closeInvite}>
                  Done
                </Button>
              </DialogFooter>
            </>
          ) : (
            <form onSubmit={(event) => void handleCreate(event)}>
              <DialogHeader>
                <DialogTitle>Invite User</DialogTitle>
                <DialogDescription>
                  Email a new person to join this tenant. If they already have an account, use Add
                  Member instead.
                </DialogDescription>
              </DialogHeader>
              <label className="mt-4 block text-sm font-medium text-foreground">
                Email address
                <Input
                  className="mt-1.5"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="off"
                  data-testid="invite-user-email-input"
                  required
                />
              </label>
              <fieldset className="mt-4">
                <legend className="text-sm font-medium">Roles</legend>
                <div className="mt-2 flex flex-col gap-1">
                  {TENANT_ROLES.map((role) => (
                    <label key={role} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedRoles.includes(role)}
                        onChange={() => toggleRole(role)}
                        data-testid={`invite-user-role-${role}`}
                      />
                      {role}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="mt-4 block text-sm font-medium text-foreground">
                Invitation validity
                <select
                  className="mt-1.5 w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
                  value={validityDays}
                  onChange={(event) =>
                    setValidityDays(Number(event.target.value) as (typeof VALIDITY_OPTIONS)[number])
                  }
                  data-testid="invite-user-validity"
                >
                  {VALIDITY_OPTIONS.map((days) => (
                    <option key={days} value={days}>
                      {days === 7 ? '7 days (Default)' : `${days} days`}
                    </option>
                  ))}
                </select>
              </label>
              {inviteError ? (
                <p className="mt-3 text-sm text-destructive" role="alert">
                  {inviteError}
                </p>
              ) : null}
              <DialogFooter className="mt-4">
                <Button type="button" variant="pill-cancel" size="pill" onClick={closeInvite}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="pill-dark"
                  size="pill"
                  disabled={!canSubmit}
                  data-testid="invite-user-submit"
                >
                  <MailPlus className="size-3.5" aria-hidden />
                  {sending ? 'Sending…' : 'Send Invitation'}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
