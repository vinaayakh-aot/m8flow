import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { FolderPlus, Pencil, Search, Shield, Trash2 } from 'lucide-react';

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
  createTenantGroup,
  deleteTenantGroup,
  fetchTenantGroups,
  grantTenantGroupRole,
  normalizeTenantGroupName,
  renameTenantGroup,
  revokeTenantGroupRole,
  TENANT_GROUP_NAME_MAX_LENGTH,
  TENANT_ROLES,
  tenantAdminErrorMessage,
  type TenantGroup,
  type TenantRole,
  validateTenantGroupName,
} from '@/lib/tenantAdminApi';

const GROUPS_PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 300;

type TenantGroupsSectionProps = {
  tenantId: string;
  existingGroupNames: string[];
  reloadKey: number;
  onChanged: () => void;
};

function nameTaken(
  candidate: string,
  existingNames: string[],
  exceptName?: string,
): boolean {
  const normalized = normalizeTenantGroupName(candidate).toLowerCase();
  const except = exceptName ? normalizeTenantGroupName(exceptName).toLowerCase() : null;
  return existingNames.some((name) => {
    const current = normalizeTenantGroupName(name).toLowerCase();
    if (except && current === except) {
      return false;
    }
    return current === normalized;
  });
}

export default function TenantGroupsSection({
  tenantId,
  existingGroupNames,
  reloadKey,
  onChanged,
}: TenantGroupsSectionProps) {
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [groups, setGroups] = useState<TenantGroup[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [groupToRename, setGroupToRename] = useState<TenantGroup | null>(null);
  const [renameName, setRenameName] = useState('');
  const [renameError, setRenameError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);

  const [groupToDelete, setGroupToDelete] = useState<TenantGroup | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [groupForRoles, setGroupForRoles] = useState<TenantGroup | null>(null);
  const [rolesError, setRolesError] = useState<string | null>(null);

  const skipSearchDebounce = useRef(true);

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
    fetchTenantGroups(tenantId, {
      search,
      offset: page * GROUPS_PAGE_SIZE,
      limit: GROUPS_PAGE_SIZE,
    })
      .then((payload) => {
        if (!cancelled) {
          setGroups(payload.groups);
          setHasMore(payload.has_more);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(tenantAdminErrorMessage(err, 'Failed to load groups'));
          setGroups([]);
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

  const createValidation = useMemo(() => {
    const formatError = validateTenantGroupName(createName);
    if (formatError) {
      return formatError;
    }
    if (nameTaken(createName, existingGroupNames)) {
      return `Group '${normalizeTenantGroupName(createName)}' already exists in this tenant.`;
    }
    return null;
  }, [createName, existingGroupNames]);

  const renameValidation = useMemo(() => {
    const formatError = validateTenantGroupName(renameName);
    if (formatError) {
      return formatError;
    }
    if (groupToRename && nameTaken(renameName, existingGroupNames, groupToRename.name)) {
      return `Group '${normalizeTenantGroupName(renameName)}' already exists in this tenant.`;
    }
    return null;
  }, [renameName, existingGroupNames, groupToRename]);

  function openCreate() {
    setCreateName('');
    setCreateError(null);
    setCreateOpen(true);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (creating) {
      return;
    }
    const normalized = normalizeTenantGroupName(createName);
    const formatError = validateTenantGroupName(createName);
    if (formatError) {
      setCreateError(formatError);
      return;
    }
    if (nameTaken(createName, existingGroupNames)) {
      setCreateError(`Group '${normalized}' already exists in this tenant.`);
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      await createTenantGroup(tenantId, normalized);
      setCreateOpen(false);
      onChanged();
    } catch (err: unknown) {
      setCreateError(tenantAdminErrorMessage(err, 'Failed to create group'));
    } finally {
      setCreating(false);
    }
  }

  function openRename(group: TenantGroup) {
    setGroupToRename(group);
    setRenameName(group.name);
    setRenameError(null);
  }

  async function handleRename(event: FormEvent) {
    event.preventDefault();
    if (!groupToRename || renaming) {
      return;
    }
    const normalized = normalizeTenantGroupName(renameName);
    const formatError = validateTenantGroupName(renameName);
    if (formatError) {
      setRenameError(formatError);
      return;
    }
    if (nameTaken(renameName, existingGroupNames, groupToRename.name)) {
      setRenameError(`Group '${normalized}' already exists in this tenant.`);
      return;
    }
    setRenaming(true);
    setRenameError(null);
    try {
      await renameTenantGroup(tenantId, groupToRename.name, normalized);
      setGroupToRename(null);
      onChanged();
    } catch (err: unknown) {
      setRenameError(tenantAdminErrorMessage(err, 'Failed to rename group'));
    } finally {
      setRenaming(false);
    }
  }

  async function handleDelete() {
    if (!groupToDelete || deleting) {
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteTenantGroup(tenantId, groupToDelete.name);
      setGroupToDelete(null);
      onChanged();
    } catch (err: unknown) {
      setError(tenantAdminErrorMessage(err, 'Failed to delete group'));
      setGroupToDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  function openRoles(group: TenantGroup) {
    setGroupForRoles(group);
    setRolesError(null);
  }

  async function toggleRole(role: TenantRole) {
    if (!groupForRoles) {
      return;
    }
    const hasRole = groupForRoles.mapped_roles.includes(role);
    setRolesError(null);
    try {
      const payload = hasRole
        ? await revokeTenantGroupRole(tenantId, groupForRoles.name, role)
        : await grantTenantGroupRole(tenantId, groupForRoles.name, role);
      setGroupForRoles(payload.group);
      onChanged();
    } catch (err: unknown) {
      setRolesError(tenantAdminErrorMessage(err, 'Failed to update group roles'));
    }
  }

  return (
    <>
      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Card variant="bordered" className="mt-6 overflow-hidden">
        <div
          className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-[22px] py-3"
          data-testid="tenant-groups-section-header"
        >
          <h2 className="text-[15px] font-semibold text-foreground">Groups</h2>
        </div>
        <div
          className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-[22px] py-3"
          data-testid="tenant-groups-toolbar"
        >
          <label className="flex min-w-0 flex-1 items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2">
            <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
            <Input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search groups…"
              className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] shadow-none outline-none focus-visible:ring-0"
              data-testid="tenant-group-search-input"
              aria-label="Search groups"
            />
          </label>
          <Button
            type="button"
            variant="pill-dark"
            size="pill"
            onClick={openCreate}
            data-testid="tenant-group-add-button"
          >
            <FolderPlus className="size-3.5" aria-hidden />
            Add Group
          </Button>
        </div>

        {loading ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">Loading groups…</p>
        ) : groups.length === 0 ? (
          <p className="px-[22px] py-6 text-sm text-muted-foreground">
            {search ? 'No groups match this search.' : 'No groups in this tenant yet.'}
          </p>
        ) : (
          <table className="w-full text-left text-sm" data-testid="tenant-group-table-container">
            <thead>
              <tr className="border-b border-border text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                <th className="px-[22px] py-3 font-medium">Group</th>
                <th className="px-[22px] py-3 font-medium">Roles</th>
                <th className="px-[22px] py-3 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.id || group.name} className="border-b border-border last:border-b-0">
                  <td
                    className="px-[22px] py-3 font-medium text-foreground"
                    data-testid={`tenant-group-name-cell-${group.id}`}
                  >
                    {group.name}
                  </td>
                  <td className="px-[22px] py-3">
                    <div className="flex flex-wrap gap-1">
                      {group.mapped_roles.length === 0 ? (
                        <span className="text-muted-foreground">None</span>
                      ) : (
                        group.mapped_roles.map((role) => (
                          <Badge
                            key={role}
                            variant="info"
                            data-testid={`tenant-group-role-chip-${group.id}-${role}`}
                          >
                            {role}
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
                      onClick={() => openRename(group)}
                      data-testid={`tenant-group-rename-button-${group.name}`}
                    >
                      <Pencil className="size-3.5" aria-hidden />
                      Rename
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => openRoles(group)}
                      data-testid={`tenant-group-manage-roles-button-${group.name}`}
                    >
                      <Shield className="size-3.5" aria-hidden />
                      Roles
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setGroupToDelete(group)}
                      data-testid={`tenant-group-remove-button-${group.name}`}
                    >
                      <Trash2 className="size-3.5" aria-hidden />
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="flex items-center justify-between gap-3 px-[22px] py-3 text-sm">
          <span data-testid="tenant-group-page-indicator" className="text-muted-foreground">
            Page {page + 1}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="pill-outline"
              size="pill"
              disabled={page === 0}
              onClick={() => setPage((current) => Math.max(0, current - 1))}
              data-testid="tenant-group-previous-page-button"
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="pill-outline"
              size="pill"
              disabled={!hasMore}
              onClick={() => setPage((current) => current + 1)}
              data-testid="tenant-group-next-page-button"
            >
              Next
            </Button>
          </div>
        </div>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={(event) => void handleCreate(event)}>
            <DialogHeader>
              <DialogTitle>Add group</DialogTitle>
              <DialogDescription>
                People stay in the tenant if you later delete the group. Roles come from
                the group, not from a separate member-role editor.
              </DialogDescription>
            </DialogHeader>
            <label className="mt-4 block text-sm font-medium text-foreground">
              Group name
              <Input
                className="mt-1.5"
                value={createName}
                onChange={(event) => {
                  setCreateName(event.target.value);
                  setCreateError(null);
                }}
                autoComplete="off"
                maxLength={TENANT_GROUP_NAME_MAX_LENGTH}
                data-testid="tenant-group-name-input"
                required
              />
            </label>
            {createError || (createName && createValidation) ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {createError || createValidation}
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
                disabled={creating || Boolean(createValidation)}
                data-testid="tenant-group-submit-button"
              >
                {creating ? 'Creating…' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(groupToRename)}
        onOpenChange={(open) => !open && setGroupToRename(null)}
      >
        <DialogContent className="sm:max-w-md" data-testid="tenant-group-rename-dialog">
          <form onSubmit={(event) => void handleRename(event)}>
            <DialogHeader>
              <DialogTitle>Rename group</DialogTitle>
              <DialogDescription>
                Members stay in the group. The name must match the API rules.
              </DialogDescription>
            </DialogHeader>
            <label className="mt-4 block text-sm font-medium text-foreground">
              Group name
              <Input
                className="mt-1.5"
                value={renameName}
                onChange={(event) => {
                  setRenameName(event.target.value);
                  setRenameError(null);
                }}
                autoComplete="off"
                maxLength={TENANT_GROUP_NAME_MAX_LENGTH}
                data-testid="tenant-group-rename-input"
                required
              />
            </label>
            {renameError || (renameName && renameValidation) ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {renameError || renameValidation}
              </p>
            ) : null}
            <DialogFooter className="mt-4">
              <Button
                type="button"
                variant="pill-cancel"
                size="pill"
                onClick={() => setGroupToRename(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="pill-dark"
                size="pill"
                disabled={renaming || Boolean(renameValidation)}
                data-testid="tenant-group-rename-submit-button"
              >
                {renaming ? 'Saving…' : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(groupToDelete)}
        onOpenChange={(open) => !open && setGroupToDelete(null)}
      >
        <DialogContent className="sm:max-w-md" data-testid="tenant-group-remove-dialog">
          <DialogHeader>
            <DialogTitle>Delete group</DialogTitle>
            <DialogDescription>
              {groupToDelete
                ? `Delete ${groupToDelete.name}? People stay in the tenant. Roles that came only from this group go away.`
                : null}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="pill-cancel"
              size="pill"
              onClick={() => setGroupToDelete(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="pill-dark"
              size="pill"
              disabled={deleting}
              onClick={() => void handleDelete()}
              data-testid="tenant-group-remove-confirm-button"
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(groupForRoles)}
        onOpenChange={(open) => !open && setGroupForRoles(null)}
      >
        <DialogContent className="sm:max-w-md" data-testid="tenant-group-roles-dialog">
          <DialogHeader>
            <DialogTitle>Group roles</DialogTitle>
            <DialogDescription>
              Members of {groupForRoles?.name} get these as effective roles. A group may
              map more than one role.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-3 flex flex-col gap-1">
            {TENANT_ROLES.map((role) => (
              <label key={role} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={groupForRoles?.mapped_roles.includes(role) ?? false}
                  onChange={() => void toggleRole(role)}
                  data-testid={`tenant-group-role-checkbox-${groupForRoles?.name ?? 'unknown'}-${role}`}
                />
                {role}
              </label>
            ))}
          </div>
          {rolesError ? (
            <p className="mt-3 text-sm text-destructive" role="alert">
              {rolesError}
            </p>
          ) : null}
          <DialogFooter className="mt-4">
            <Button
              type="button"
              variant="pill-cancel"
              size="pill"
              onClick={() => setGroupForRoles(null)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
