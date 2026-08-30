import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Plus } from 'lucide-react';

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
import {
  connectorsErrorMessage,
  deactivateConnectorProfile,
  deleteConnectorProfile,
  fetchConnectorProfiles,
  fetchConnectorTemplate,
  updateConnectorProfile,
  type ConnectorProfile,
  type ConnectorTemplate,
} from '@/lib/connectorsApi';

import { ConnectorsGate, useConnectorsContext } from './ConnectorsGate';

const TITLE = 'Connector profiles';

export default function ConnectorProfilesPage() {
  return (
    <ConnectorsGate title={TITLE} requireTenant>
      <ConnectorProfilesBody />
    </ConnectorsGate>
  );
}

function ConnectorProfilesBody() {
  const { connectorId = '' } = useParams();
  const navigate = useNavigate();
  const { scopedTenantId, canManageConnectorProfiles } = useConnectorsContext();
  const [template, setTemplate] = useState<ConnectorTemplate | null>(null);
  const [profiles, setProfiles] = useState<ConnectorProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ConnectorProfile | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedTemplate, loadedProfiles] = await Promise.all([
        fetchConnectorTemplate(connectorId),
        fetchConnectorProfiles({
          connectorType: connectorId,
          tenantId: scopedTenantId,
        }),
      ]);
      setTemplate(loadedTemplate);
      setProfiles(loadedProfiles);
    } catch (err: unknown) {
      setError(connectorsErrorMessage(err, 'Could not load profiles.'));
      setTemplate(null);
      setProfiles([]);
    } finally {
      setLoading(false);
    }
  }, [connectorId, scopedTenantId]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  const ordered = useMemo(
    () =>
      [...profiles].sort((a, b) => {
        if (a.is_active !== b.is_active) {
          return a.is_active ? -1 : 1;
        }
        return a.profile_name.localeCompare(b.profile_name);
      }),
    [profiles],
  );

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null);
    try {
      await action();
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setActionError(connectorsErrorMessage(err, 'Could not update the profile.'));
    }
  }

  const heading = template?.name ? `${template.name} profiles` : TITLE;

  return (
    <main className="flex-1 px-11 py-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-sm text-muted-foreground">
            <Link to="/connectors" className="hover:underline">
              Connectors
            </Link>
          </p>
          <h1 className="font-display text-[32px] font-semibold tracking-tight">{heading}</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Saved credential sets a Service Task can select by name.
          </p>
        </div>
        {canManageConnectorProfiles ? (
          <Button asChild variant="pill-dark" size="pill">
            <Link to={`/connectors/${encodeURIComponent(connectorId)}/profiles/new`}>
              <Plus className="size-3.5" aria-hidden />
              Add profile
            </Link>
          </Button>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      {actionError ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {actionError}
        </p>
      ) : null}

      <Card variant="bordered" className="overflow-hidden">
        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading profiles…</p>
        ) : ordered.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground" data-testid="connector-profiles-empty">
            No profiles yet. Add one to select it from a Service Task.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">Profile</th>
                <th className="px-[22px] py-3 font-medium">Identifier</th>
                <th className="px-[22px] py-3 font-medium">Credentials</th>
                {canManageConnectorProfiles ? (
                  <th className="px-[22px] py-3 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {ordered.map((profile) => (
                <tr
                  key={profile.id}
                  className={`border-b border-border last:border-b-0 ${profile.is_active ? '' : 'opacity-55'}`}
                  data-testid={`connector-profile-row-${profile.profile_name}`}
                >
                  <td className="px-[22px] py-3">
                    <div className="font-medium text-foreground">{profile.display_name}</div>
                    {!profile.is_active ? (
                      <span className="mt-1 inline-block text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                        Inactive
                      </span>
                    ) : null}
                    {profile.description ? (
                      <div className="mt-1 text-[13px] text-muted-foreground">{profile.description}</div>
                    ) : null}
                  </td>
                  <td className="px-[22px] py-3 font-mono text-[13px] text-muted-foreground">
                    {profile.profile_name}
                  </td>
                  <td className="px-[22px] py-3 text-muted-foreground">
                    {profile.configured_secrets.length
                      ? profile.configured_secrets.join(', ')
                      : 'None stored'}
                  </td>
                  {canManageConnectorProfiles ? (
                    <td className="px-[22px] py-3 text-right">
                      <div className="flex flex-wrap justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            navigate(
                              `/connectors/${encodeURIComponent(connectorId)}/profiles/${profile.id}/edit`,
                            )
                          }
                        >
                          Edit
                        </Button>
                        {profile.is_active ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => void runAction(() => deactivateConnectorProfile(profile.id, scopedTenantId))}
                          >
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              void runAction(() =>
                                updateConnectorProfile(profile.id, { is_active: true }, scopedTenantId),
                              )
                            }
                          >
                            Reactivate
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setPendingDelete(profile)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete this profile permanently?</DialogTitle>
            <DialogDescription>
              This removes “{pendingDelete?.display_name ?? ''}” and its stored credentials. Any
              process model that still selects this profile will fail when it runs. Deactivate
              instead if you may need it again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="pill-cancel" size="pill" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                const target = pendingDelete;
                setPendingDelete(null);
                if (target) {
                  void runAction(() => deleteConnectorProfile(target.id, scopedTenantId));
                }
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
