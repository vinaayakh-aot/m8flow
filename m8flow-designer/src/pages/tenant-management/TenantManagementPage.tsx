import { useOutletContext } from 'react-router-dom';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/card';
import { getActiveTenantDisplayLabel, getSelectedTenantId } from '@/lib/auth';
import TenantAdminPanel from './TenantAdminPanel';

/**
 * Tenant admin for the active tenant (tenant-admin) or the sidebar tenant
 * (super-admin). Invitation management is composed onto the shared panel for
 * super-admin only. Super-admins can also reach the same panel by expanding a
 * tenant registry row — that path does not set `m8flow_selected_tenant`.
 */
export default function TenantManagementPage() {
  const {
    scopedTenantId,
    isSuperAdmin,
    canManageTenant = false,
    refreshTenants,
  } = useOutletContext<AppShellOutletContext>();

  const tenantId = isSuperAdmin ? scopedTenantId : getSelectedTenantId();
  const needsTenant = canManageTenant && !tenantId;

  if (!canManageTenant) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="font-display text-[32px] font-semibold tracking-tight">
            Tenant Management
          </h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Not available</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Tenant Management is for tenant admins and platform admins. Your role
            cannot list or manage members.
          </p>
        </Card>
      </main>
    );
  }

  if (needsTenant || !tenantId) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="font-display text-[32px] font-semibold tracking-tight">
            Tenant Management
          </h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Choose a tenant</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Members are tenant-scoped. Select a concrete tenant in the sidebar — All
            Tenants is not supported here.
          </p>
        </Card>
      </main>
    );
  }

  return (
    <TenantAdminPanel
      tenantId={tenantId}
      tenantName={getActiveTenantDisplayLabel() ?? tenantId}
      isSuperAdmin={isSuperAdmin}
      refreshTenants={refreshTenants}
    />
  );
}
