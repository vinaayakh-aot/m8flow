import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';

import { fetchCapabilities, fetchOrganizationMemberships, fetchTenants, type TenantSummary } from '@/lib/api';
import {
  getActiveTenantDisplayLabel,
  getCurrentUser,
  isSuperAdmin,
  logout,
} from '@/lib/auth';
import { Sidebar } from './Sidebar';
import { persistTenantId, readPersistedTenantId } from '@/lib/selectedTenant';

export type AppShellOutletContext = {
  /**
   * Tenant id passed to Home/Processes data fetches.
   * Super-admin: selected sidebar tenant, or `null` for All Tenants.
   * Regular user: always `null` (cookie is the source of truth server-side).
   */
  scopedTenantId: string | null;
  /** Raw sidebar selection; `null` means All Tenants when selector is shown. */
  selectedTenantId: string | null;
  isSuperAdmin: boolean;
  /** Whether the user may start/delete process models (UI gating only —
   * the backend still enforces authorization). Optional so existing test
   * harnesses that build a minimal context still type-check; AppShell always
   * provides it, and consumers treat absent as "cannot manage". */
  canManageProcesses?: boolean;
  /** YAML authentications grants (integrator / tenant-admin / viewer read). */
  canReadAuthentications?: boolean;
  canManageAuthentications?: boolean;
  /** YAML secrets grants (integrator / viewer / tenant-admin read). */
  canReadSecrets?: boolean;
  canManageSecrets?: boolean;
  /** YAML connectors-grouped read (tenant-admin / editor / integrator). */
  canReadConnectors?: boolean;
  /** YAML connector-profile writes (tenant-admin / integrator). */
  canManageConnectorProfiles?: boolean;
  /** Advisory Tenant Management hint. Members/groups APIs still enforce allow_uri. */
  canManageTenant?: boolean;
  /** Super-admin switcher should reload after registry create/rename. */
  refreshTenants?: () => void;
  /** Super-admin registry rows, used to resolve display names on tenant admin. */
  tenants?: TenantSummary[];
};

/**
 * Shared chrome: Sidebar + tenant/logout wiring + `<Outlet />` for page content.
 */
export function AppShell() {
  const user = getCurrentUser();
  const superAdmin = isSuperAdmin();
  const [selectedTenantId, setSelectedTenantIdState] = useState<string | null>(
    () => readPersistedTenantId(),
  );
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [tenantsReloadKey, setTenantsReloadKey] = useState(0);
  const [canManage, setCanManage] = useState(false);
  const [canReadAuthentications, setCanReadAuthentications] = useState(false);
  const [canManageAuthentications, setCanManageAuthentications] = useState(false);
  const [canReadSecrets, setCanReadSecrets] = useState(false);
  const [canManageSecrets, setCanManageSecrets] = useState(false);
  const [canReadConnectors, setCanReadConnectors] = useState(false);
  const [canManageConnectorProfiles, setCanManageConnectorProfiles] = useState(false);
  const [canManageTenant, setCanManageTenant] = useState(false);
  const [activeTenantLabel, setActiveTenantLabel] = useState<string | null>(() =>
    superAdmin ? null : getActiveTenantDisplayLabel(),
  );

  useEffect(() => {
    let cancelled = false;
    fetchCapabilities()
      .then((caps) => {
        if (!cancelled) {
          setCanManage(Boolean(caps.can_manage_processes));
          setCanReadAuthentications(Boolean(caps.can_read_authentications));
          setCanManageAuthentications(Boolean(caps.can_manage_authentications));
          setCanReadSecrets(Boolean(caps.can_read_secrets));
          setCanManageSecrets(Boolean(caps.can_manage_secrets));
          setCanReadConnectors(Boolean(caps.can_read_connectors));
          setCanManageConnectorProfiles(Boolean(caps.can_manage_connector_profiles));
          setCanManageTenant(Boolean(caps.can_manage_tenant));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCanManage(false);
          setCanReadAuthentications(false);
          setCanManageAuthentications(false);
          setCanReadSecrets(false);
          setCanManageSecrets(false);
          setCanReadConnectors(false);
          setCanManageConnectorProfiles(false);
          setCanManageTenant(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function setSelectedTenantId(tenantId: string | null) {
    persistTenantId(tenantId);
    setSelectedTenantIdState(tenantId);
  }

  useEffect(() => {
    if (!superAdmin) {
      return;
    }
    let cancelled = false;
    fetchTenants()
      .then((rows) => {
        if (!cancelled) {
          setTenants(rows.map((row) => ({ id: row.id, name: row.name || row.id })));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTenants([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [superAdmin, tenantsReloadKey]);

  useEffect(() => {
    if (superAdmin) {
      setActiveTenantLabel(null);
      return;
    }
    setActiveTenantLabel(getActiveTenantDisplayLabel());
    let cancelled = false;
    fetchOrganizationMemberships()
      .then((rows) => {
        if (!cancelled) {
          setActiveTenantLabel(getActiveTenantDisplayLabel(rows));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setActiveTenantLabel(getActiveTenantDisplayLabel());
        }
      });
    return () => {
      cancelled = true;
    };
  }, [superAdmin]);

  const scopedTenantId = superAdmin ? selectedTenantId : null;
  const userLabel = user?.username ?? user?.email ?? 'unknown user';
  const outletContext: AppShellOutletContext = {
    scopedTenantId,
    selectedTenantId,
    isSuperAdmin: superAdmin,
    canManageProcesses: canManage,
    canReadAuthentications,
    canManageAuthentications,
    canReadSecrets,
    canManageSecrets,
    canReadConnectors,
    canManageConnectorProfiles,
    canManageTenant,
    refreshTenants: () => setTenantsReloadKey((key) => key + 1),
    tenants,
  };
  const tenantOptions =
    selectedTenantId && !tenants.some((t) => t.id === selectedTenantId)
      ? [{ id: selectedTenantId, name: selectedTenantId }, ...tenants]
      : tenants;

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar
        showTenantSelector={superAdmin}
        selectedTenantId={selectedTenantId}
        onTenantChange={setSelectedTenantId}
        tenants={tenantOptions}
        activeTenantLabel={activeTenantLabel}
        onLogout={logout}
        userLabel={userLabel}
        showAuthentications={canReadAuthentications}
        showConfiguration={canReadSecrets}
        showConnectors={canReadConnectors}
        showTenantsNav={superAdmin}
        showTenantManagement={canManageTenant && !superAdmin}
      />
      <Outlet context={outletContext} />
    </div>
  );
}
