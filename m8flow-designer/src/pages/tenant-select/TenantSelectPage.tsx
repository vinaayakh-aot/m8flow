import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { fetchOrganizationMemberships } from '@/lib/api';
import {
  clearSelectedTenantCookie,
  finalizeTenantLogin,
  getOrganizationMemberships,
  GLOBAL_ADMIN_LANDING_PATH,
  isLoggedIn,
  login,
  loginAsPlatformAdmin,
  logout,
  type OrganizationMembership,
} from '@/lib/auth';

function designerRootUrl(): string {
  return `${window.location.origin}/`;
}

function globalAdminLandingUrl(): string {
  return `${window.location.origin}${GLOBAL_ADMIN_LANDING_PATH}`;
}

function mergeOrganizationMemberships(
  currentMemberships: OrganizationMembership[],
  resolvedMemberships: OrganizationMembership[],
): OrganizationMembership[] {
  const resolvedByKey = new Map<string, OrganizationMembership>();
  for (const membership of resolvedMemberships) {
    if (membership.id) {
      resolvedByKey.set(`id:${membership.id}`, membership);
    }
    resolvedByKey.set(`alias:${membership.alias}`, membership);
  }

  return currentMemberships.map((membership) => {
    const resolved =
      (membership.id && resolvedByKey.get(`id:${membership.id}`)) ||
      resolvedByKey.get(`alias:${membership.alias}`);
    if (!resolved) {
      return membership;
    }
    return {
      alias: membership.alias,
      id: resolved.id || membership.id,
      name: resolved.name || membership.name,
    };
  });
}

export default function TenantSelectPage() {
  const loggedIn = isLoggedIn();
  const tokenOrganizations = getOrganizationMemberships();
  const organizationMembershipsKey = JSON.stringify(tokenOrganizations);
  const [organizations, setOrganizations] = useState<OrganizationMembership[]>(
    () => tokenOrganizations,
  );
  const [directoryResolved, setDirectoryResolved] = useState(
    () => !loggedIn || tokenOrganizations.length > 0,
  );
  const autoFinalizeStarted = useRef(false);

  useEffect(() => {
    setOrganizations(tokenOrganizations);
    // tokenOrganizations is rebuilt each render; the JSON key is the actual dependency.
  }, [organizationMembershipsKey]);

  useEffect(() => {
    if (!loggedIn) {
      setDirectoryResolved(true);
      return;
    }

    const needsDirectory =
      tokenOrganizations.length === 0 ||
      tokenOrganizations.some((organization) => !organization.name?.trim());
    if (!needsDirectory) {
      setDirectoryResolved(true);
      return;
    }

    let ignore = false;
    fetchOrganizationMemberships()
      .then((resolved) => {
        if (ignore) {
          return;
        }
        if (tokenOrganizations.length === 0) {
          setOrganizations(resolved);
        } else {
          setOrganizations(mergeOrganizationMemberships(tokenOrganizations, resolved));
        }
        setDirectoryResolved(true);
      })
      .catch(() => {
        if (ignore) {
          return;
        }
        setOrganizations(tokenOrganizations);
        setDirectoryResolved(true);
      });

    return () => {
      ignore = true;
    };
  }, [loggedIn, organizationMembershipsKey]);

  useEffect(() => {
    if (!loggedIn || !directoryResolved || organizations.length !== 1 || autoFinalizeStarted.current) {
      return;
    }
    autoFinalizeStarted.current = true;
    finalizeTenantLogin(organizations[0]);
  }, [loggedIn, directoryResolved, organizations]);

  function handleSharedRealmSignIn() {
    clearSelectedTenantCookie();
    login({ redirectUrl: designerRootUrl() });
  }

  function handlePlatformAdminSignIn() {
    clearSelectedTenantCookie();
    loginAsPlatformAdmin({ redirectUrl: globalAdminLandingUrl() });
  }

  if (!loggedIn) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-2">
            <h1 className="font-display text-3xl font-semibold tracking-tight">Sign in to M8Flow</h1>
            <p className="text-sm text-muted-foreground">
              Sign in with your organization account, or continue as a platform admin.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" onClick={handleSharedRealmSignIn} data-testid="shared-realm-sign-in-button">
              Sign In
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={handlePlatformAdminSignIn}
              data-testid="global-admin-sign-in-button"
            >
              Platform Admin Sign In
            </Button>
          </div>
        </div>
      </main>
    );
  }

  if (organizations.length === 0 && !directoryResolved) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <p className="text-sm text-muted-foreground" data-testid="tenant-membership-loading">
          Checking organization membership…
        </p>
      </main>
    );
  }

  if (organizations.length === 0) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-2">
            <h1 className="font-display text-3xl font-semibold tracking-tight">No tenants available</h1>
            <p className="rounded-lg border border-border bg-card px-4 py-3 text-sm">
              This account is not a member of any organization.
            </p>
            <p className="text-sm text-muted-foreground" data-testid="no-tenant-access-message">
              Contact an administrator to be added to a tenant, then sign in again.
            </p>
          </div>
          <Button type="button" variant="ghost" onClick={() => logout()} data-testid="back-to-login-button">
            Back to login
          </Button>
        </div>
      </main>
    );
  }

  if (organizations.length === 1) {
    const tenant = organizations[0];
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <div className="w-full max-w-md space-y-2">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Finalizing tenant access</h1>
          <p className="text-sm text-muted-foreground">
            Continuing into {tenant.name || tenant.alias}…
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
      <div className="w-full max-w-md space-y-6">
        <div className="space-y-2">
          <h1 className="font-display text-3xl font-semibold tracking-tight">Select a tenant</h1>
          <p className="text-sm text-muted-foreground">Choose the organization you want to work in.</p>
        </div>
        <div className="flex flex-col gap-2">
          {organizations.map((organization) => {
            const displayName = organization.name || organization.alias;
            const showAlias = displayName !== organization.alias;
            return (
              <Button
                key={organization.alias}
                type="button"
                variant="outline"
                className="h-auto justify-between gap-3 py-3 text-left whitespace-normal"
                onClick={() => finalizeTenantLogin(organization)}
                data-testid={`organization-option-${organization.alias}`}
              >
                <span className="min-w-0 flex-1 font-semibold">{displayName}</span>
                {showAlias ? (
                  <span className="max-w-[45%] shrink-0 text-xs font-normal text-muted-foreground">
                    {organization.alias}
                  </span>
                ) : null}
              </Button>
            );
          })}
        </div>
      </div>
    </main>
  );
}
