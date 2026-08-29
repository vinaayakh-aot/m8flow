import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { MailPlus, Pencil, Plus, Search, UserPlus, Users } from 'lucide-react';

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
  addTenantGroupMember,
  addTenantMember,
  fetchAvailableTenantUsers,
  fetchTenantGroups,
  fetchTenantMembers,
  removeTenantGroupMember,
  removeTenantMember,
  tenantAdminErrorMessage,
  type TenantAvailableUser,
  type TenantGroup,
  type TenantMember,
} from '@/lib/tenantAdminApi';
import TenantGroupsSection from './TenantGroupsSection';
import InvitationManagementSection from './InvitationManagementSection';
import {
  MAX_TENANT_NAME_LENGTH,
  tenantsErrorMessage,
  updateTenantName,
  validateTenantDisplayName,
} from '@/lib/tenantsApi';

const MEMBERS_PAGE_SIZE = 10;
const PICKER_GROUPS_LIMIT = 100;
const AVAILABLE_USERS_PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 300;

export type TenantAdminPanelProps = {
  tenantId: string;
  tenantName: string;
  isSuperAdmin: boolean;
  refreshTenants?: () => void;
  onTenantNameChange?: (name: string) => void;
  embedded?: boolean;
};

/**
 * Members, groups, role grants, and (for super-admin) invitation management
 * for one tenant. The page and the tenant-registry row expansion both render
 * this panel so they stay in sync. Does not set `m8flow_selected_tenant`.
 */
export default function TenantAdminPanel({
  tenantId,
  tenantName: initialTenantName,
  isSuperAdmin,
  refreshTenants,
  onTenantNameChange,
  embedded = false,
}: TenantAdminPanelProps) {
  const [tenantName, setTenantName] = useState(initialTenantName);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [members, setMembers] = useState<TenantMember[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [inviteOpen, setInviteOpen] = useState(false);

  const [groups, setGroups] = useState<TenantGroup[]>([]);

  const [renameOpen, setRenameOpen] = useState(false);
  const [renameName, setRenameName] = useState('');
  const [renameError, setRenameError] = useState<string | null>(null);
  const [savingName, setSavingName] = useState(false);

  const [addOpen, setAddOpen] = useState(false);
  const [availableUsers, setAvailableUsers] = useState<TenantAvailableUser[]>([]);
  const [availableSearch, setAvailableSearch] = useState('');
  const [availableOffset, setAvailableOffset] = useState(0);
  const [availableHasMore, setAvailableHasMore] = useState(false);
  const [loadingAvailable, setLoadingAvailable] = useState(false);
  const [selectedUsername, setSelectedUsername] = useState<string | null>(null);
  const [addGroupNames, setAddGroupNames] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [memberToRemove, setMemberToRemove] = useState<TenantMember | null>(null);
  const [removing, setRemoving] = useState(false);

  const [memberForGroups, setMemberForGroups] = useState<TenantMember | null>(null);
  const [groupSelection, setGroupSelection] = useState<Set<string>>(new Set());
  const [savingGroups, setSavingGroups] = useState(false);
  const [groupsError, setGroupsError] = useState<string | null>(null);

  const skipSearchDebounce = useRef(true);

  useEffect(() => {
    setTenantName(initialTenantName);
  }, [initialTenantName]);

  useEffect(() => {
    if (skipSearchDebounce.current) {
      skipSearchDebounce.current = false;
      return undefined;
    }
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(0);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchTenantMembers(tenantId, {
      search,
      offset: page * MEMBERS_PAGE_SIZE,
      limit: MEMBERS_PAGE_SIZE,
    })
      .then((payload) => {
        if (!cancelled) {
          setMembers(payload.members);
          setHasMore(payload.has_more);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(tenantAdminErrorMessage(err, 'Failed to load members'));
          setMembers([]);
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
  }, [tenantId, search, page, reloadKey]);

  useEffect(() => {
    let cancelled = false;
    fetchTenantGroups(tenantId, { limit: PICKER_GROUPS_LIMIT })
      .then((payload) => {
        if (!cancelled) {
          setGroups(payload.groups);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setGroups([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tenantId, reloadKey]);

  useEffect(() => {
    if (!addOpen || !tenantId) {
      return undefined;
    }
    let cancelled = false;
    setLoadingAvailable(true);
    fetchAvailableTenantUsers(tenantId, {
      search: availableSearch.trim(),
      offset: availableOffset,
      limit: AVAILABLE_USERS_PAGE_SIZE,
    })
      .then((payload) => {
        if (!cancelled) {
          setAvailableUsers(payload.users);
          setAvailableHasMore(payload.has_more);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setAddError(tenantAdminErrorMessage(err, 'Failed to load available users'));
          setAvailableUsers([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingAvailable(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [addOpen, tenantId, availableSearch, availableOffset]);

  const groupNames = useMemo(() => groups.map((group) => group.name), [groups]);

  function openRename() {
    setRenameName(tenantName);
    setRenameError(null);
    setRenameOpen(true);
  }

  async function handleRename(event: FormEvent) {
    event.preventDefault();
    if (!tenantId || savingName) {
      return;
    }
    const trimmed = renameName.trim();
    const nameError = validateTenantDisplayName(trimmed);
    if (nameError) {
      setRenameError(nameError);
      return;
    }
    setSavingName(true);
    setRenameError(null);
    try {
      await updateTenantName(tenantId, trimmed);
      setTenantName(trimmed);
      setRenameOpen(false);
      onTenantNameChange?.(trimmed);
      refreshTenants?.();
    } catch (err: unknown) {
      setRenameError(tenantsErrorMessage(err, 'Failed to rename tenant'));
    } finally {
      setSavingName(false);
    }
  }

  function openAdd() {
    setAddOpen(true);
    setAvailableSearch('');
    setAvailableOffset(0);
    setSelectedUsername(null);
    setAddGroupNames([]);
    setAddError(null);
  }

  function toggleAddGroup(name: string) {
    setAddGroupNames((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  }

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    if (!tenantId || !selectedUsername || adding) {
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      await addTenantMember(tenantId, {
        username: selectedUsername,
        group_names: addGroupNames.length > 0 ? addGroupNames : undefined,
      });
      setAddOpen(false);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setAddError(tenantAdminErrorMessage(err, 'Failed to add member'));
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove() {
    if (!tenantId || !memberToRemove || removing) {
      return;
    }
    setRemoving(true);
    setError(null);
    try {
      await removeTenantMember(tenantId, memberToRemove.username);
      setMemberToRemove(null);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setError(tenantAdminErrorMessage(err, 'Failed to remove member'));
      setMemberToRemove(null);
    } finally {
      setRemoving(false);
    }
  }

  function openManageGroups(member: TenantMember) {
    setMemberForGroups(member);
    setGroupSelection(new Set(member.groups.map((group) => group.name)));
    setGroupsError(null);
  }

  function toggleGroupSelection(name: string) {
    setGroupSelection((current) => {
      const next = new Set(current);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  async function handleSaveGroups() {
    if (!tenantId || !memberForGroups || savingGroups) {
      return;
    }
    const current = new Set(memberForGroups.groups.map((group) => group.name));
    const toAdd = [...groupSelection].filter((name) => !current.has(name));
    const toRemove = [...current].filter((name) => !groupSelection.has(name));
    setSavingGroups(true);
    setGroupsError(null);
    try {
      await Promise.all([
        ...toAdd.map((name) => addTenantGroupMember(tenantId, name, memberForGroups.username)),
        ...toRemove.map((name) =>
          removeTenantGroupMember(tenantId, name, memberForGroups.username),
        ),
      ]);
      setMemberForGroups(null);
      setReloadKey((key) => key + 1);
    } catch (err: unknown) {
      setGroupsError(tenantAdminErrorMessage(err, 'Failed to update groups'));
    } finally {
      setSavingGroups(false);
    }
  }

  const Wrapper = embedded ? 'div' : 'main';

  return (
    <Wrapper className={embedded ? undefined : 'flex-1 px-11 py-10'}>
      {embedded ? (
        <p className="mb-4 text-sm text-muted-foreground">
          Add existing users as members and manage groups and roles associated with{' '}
          <span className="font-medium text-foreground">{tenantName || tenantId}</span>.
        </p>
      ) : (
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-[32px] font-semibold tracking-tight">
              Tenant Management
            </h1>
            <p className="mt-1 max-w-xl text-sm text-muted-foreground">
              Add existing users as members, manage groups, and grant roles on groups
              for{' '}
              <span className="font-medium text-foreground">{tenantName || tenantId}</span>.
              Members show effective roles from their groups.
              {isSuperAdmin
                ? ' Invitation management is available here for platform admins.'
                : ''}
            </p>
          </div>
          <Button
            type="button"
            variant="pill-outline"
            size="pill"
            onClick={openRename}
            data-testid="tenant-management-edit-button"
          >
            <Pencil className="size-3.5" aria-hidden />
            Edit Tenant
          </Button>
        </div>
      )}

      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Card variant="bordered" className="overflow-hidden">
        <div
          className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-[22px] py-3"
          data-testid="tenant-members-toolbar"
        >
          <label className="flex min-w-0 flex-1 items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2">
            <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
            <Input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search tenant members…"
              className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] shadow-none outline-none focus-visible:ring-0"
              data-testid="tenant-member-search-input"
              aria-label="Search tenant members"
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            {isSuperAdmin ? (
              <Button
                type="button"
                variant="pill-outline"
                size="pill"
                onClick={() => setInviteOpen(true)}
                data-testid="tenant-invite-user-button"
              >
                <MailPlus className="size-3.5" aria-hidden />
                Invite User
              </Button>
            ) : null}
            <Button
              type="button"
              variant="pill-dark"
              size="pill"
              onClick={openAdd}
              data-testid="tenant-member-add-button"
            >
              <UserPlus className="size-3.5" aria-hidden />
              Add Member
            </Button>
          </div>
        </div>

        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading members…</p>
        ) : members.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">
            {search ? 'No members match this search.' : 'No members in this tenant yet.'}
          </p>
        ) : (
          <table className="w-full text-left text-sm" data-testid="tenant-member-table-container">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">Member</th>
                <th className="px-[22px] py-3 font-medium">Effective roles</th>
                <th className="px-[22px] py-3 font-medium">Groups</th>
                <th className="px-[22px] py-3 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.username} className="border-b border-border last:border-b-0">
                  <td className="px-[22px] py-3">
                    <div className="font-medium text-foreground">
                      {member.display_name || member.username}
                    </div>
                    <div className="text-[13px] text-muted-foreground">{member.username}</div>
                  </td>
                  <td className="px-[22px] py-3">
                    <div className="flex flex-wrap gap-1">
                      {member.roles.length === 0 ? (
                        <span className="text-muted-foreground">None</span>
                      ) : (
                        member.roles.map((role) => (
                          <Badge
                            key={role}
                            variant="info"
                            data-testid={`tenant-member-role-chip-${member.username}-${role}`}
                          >
                            {role}
                          </Badge>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-[22px] py-3">
                    <div className="flex flex-wrap gap-1">
                      {member.groups.length === 0 ? (
                        <span className="text-muted-foreground">None</span>
                      ) : (
                        member.groups.map((group) => (
                          <Badge
                            key={group.id || group.name}
                            variant="outline"
                            data-testid={`tenant-member-group-chip-${member.username}-${group.name}`}
                          >
                            {group.name}
                          </Badge>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-[22px] py-3 text-right whitespace-nowrap">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => openManageGroups(member)}
                      data-testid={`tenant-member-manage-groups-button-${member.username}`}
                    >
                      <Users className="size-3.5" aria-hidden />
                      Groups
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setMemberToRemove(member)}
                      data-testid={`tenant-member-remove-button-${member.username}`}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="flex items-center justify-between gap-3 px-[22px] py-3 text-sm">
          <span data-testid="tenant-member-page-indicator" className="text-muted-foreground">
            Page {page + 1}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="pill-outline"
              size="pill"
              disabled={page === 0}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
              data-testid="tenant-member-previous-page-button"
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="pill-outline"
              size="pill"
              disabled={!hasMore}
              onClick={() => setPage((current) => current + 1)}
              data-testid="tenant-member-next-page-button"
            >
              Next
            </Button>
          </div>
        </div>
      </Card>

      {isSuperAdmin && tenantId ? (
        <InvitationManagementSection
          tenantId={tenantId}
          inviteOpen={inviteOpen}
          onInviteOpenChange={setInviteOpen}
        />
      ) : null}

      {tenantId ? (
        <TenantGroupsSection
          tenantId={tenantId}
          existingGroupNames={groupNames}
          reloadKey={reloadKey}
          onChanged={() => setReloadKey((key) => key + 1)}
        />
      ) : null}

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={(event) => void handleRename(event)}>
            <DialogHeader>
              <DialogTitle>Edit Tenant</DialogTitle>
              <DialogDescription>
                The alias stays the same. Only the display name changes.
              </DialogDescription>
            </DialogHeader>
            <label className="mt-4 block text-sm font-medium text-foreground">
              Tenant name
              <Input
                className="mt-1.5"
                value={renameName}
                onChange={(event) => setRenameName(event.target.value)}
                autoComplete="off"
                maxLength={MAX_TENANT_NAME_LENGTH}
                data-testid="tenant-name"
                required
              />
            </label>
            {renameError ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {renameError}
              </p>
            ) : null}
            <DialogFooter className="mt-4">
              <Button type="button" variant="pill-cancel" size="pill" onClick={() => setRenameOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="pill-dark"
                size="pill"
                disabled={!renameName.trim() || savingName}
                data-testid="tenant-save"
              >
                {savingName ? 'Saving…' : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-lg">
          <form onSubmit={(event) => void handleAdd(event)}>
            <DialogHeader>
              <DialogTitle>Add Member</DialogTitle>
              <DialogDescription>
                Pick an existing shared-realm user. This is not an email invitation.
              </DialogDescription>
            </DialogHeader>
            <label className="mt-4 flex items-center gap-2 rounded-full border border-border px-3 py-2">
              <Search className="size-4 text-muted-foreground" aria-hidden />
              <Input
                type="search"
                value={availableSearch}
                onChange={(event) => {
                  setAvailableSearch(event.target.value);
                  setAvailableOffset(0);
                }}
                placeholder="Search available users…"
                className="h-auto border-none p-0 shadow-none focus-visible:ring-0"
                aria-label="Search available users"
              />
            </label>
            <div className="mt-3 max-h-48 overflow-y-auto rounded-lg border border-border">
              {loadingAvailable ? (
                <p className="px-3 py-3 text-sm text-muted-foreground">Loading users…</p>
              ) : availableUsers.length === 0 ? (
                <p className="px-3 py-3 text-sm text-muted-foreground">No available users.</p>
              ) : (
                availableUsers.map((user) => (
                  <label
                    key={user.username}
                    className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-muted"
                    data-testid={`tenant-available-user-${user.username}`}
                    onClick={() => setSelectedUsername(user.username)}
                  >
                    <input
                      type="radio"
                      name="available-user"
                      checked={selectedUsername === user.username}
                      onChange={() => setSelectedUsername(user.username)}
                    />
                    <span>
                      <span className="font-medium">{user.display_name || user.username}</span>
                      <span className="ml-2 text-muted-foreground">{user.username}</span>
                    </span>
                  </label>
                ))
              )}
            </div>
            {availableHasMore || availableOffset > 0 ? (
              <div className="mt-2 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={availableOffset === 0}
                  onClick={() =>
                    setAvailableOffset((current) => Math.max(0, current - AVAILABLE_USERS_PAGE_SIZE))
                  }
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={!availableHasMore}
                  onClick={() => setAvailableOffset((current) => current + AVAILABLE_USERS_PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            ) : null}
            {groupNames.length > 0 ? (
              <fieldset className="mt-4">
                <legend className="text-sm font-medium">Optional groups</legend>
                <div className="mt-2 flex flex-col gap-1">
                  {groupNames.map((name) => (
                    <label key={name} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={addGroupNames.includes(name)}
                        onChange={() => toggleAddGroup(name)}
                        data-testid={`tenant-add-member-group-${name}`}
                      />
                      {name}
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}
            {addError ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {addError}
              </p>
            ) : null}
            <DialogFooter className="mt-4">
              <Button type="button" variant="pill-cancel" size="pill" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="pill-dark"
                size="pill"
                disabled={!selectedUsername || adding}
                data-testid="tenant-member-add-submit"
              >
                <Plus className="size-3.5" aria-hidden />
                {adding ? 'Adding…' : 'Add'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(memberToRemove)} onOpenChange={(open) => !open && setMemberToRemove(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove member</DialogTitle>
            <DialogDescription>
              {memberToRemove
                ? `Remove ${memberToRemove.display_name || memberToRemove.username} from this tenant? They will lose group memberships here.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="pill-cancel" size="pill" onClick={() => setMemberToRemove(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="pill-dark"
              size="pill"
              disabled={removing}
              onClick={() => void handleRemove()}
              data-testid="tenant-member-remove-confirm-button"
            >
              {removing ? 'Removing…' : 'Remove'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(memberForGroups)}
        onOpenChange={(open) => !open && setMemberForGroups(null)}
      >
        <DialogContent className="sm:max-w-md" data-testid="tenant-member-groups-dialog">
          <DialogHeader>
            <DialogTitle>Member groups</DialogTitle>
            <DialogDescription>
              Effective roles come from these groups. There is no separate member-role
              editor.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-3 flex flex-col gap-1">
            {groups.length === 0 ? (
              <p className="text-sm text-muted-foreground">No groups in this tenant yet.</p>
            ) : (
              groups.map((group) => (
                <label key={group.id || group.name} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={groupSelection.has(group.name)}
                    onChange={() => toggleGroupSelection(group.name)}
                    data-testid={`tenant-member-group-toggle-${group.name}`}
                  />
                  {group.name}
                </label>
              ))
            )}
          </div>
          {groupsError ? (
            <p className="mt-3 text-sm text-destructive" role="alert">
              {groupsError}
            </p>
          ) : null}
          <DialogFooter className="mt-4">
            <Button
              type="button"
              variant="pill-cancel"
              size="pill"
              onClick={() => setMemberForGroups(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="pill-dark"
              size="pill"
              disabled={savingGroups}
              onClick={() => void handleSaveGroups()}
              data-testid="tenant-member-groups-save"
            >
              {savingGroups ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Wrapper>
  );
}
