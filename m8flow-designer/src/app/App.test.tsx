import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppRoutes } from './App';

const mockShouldShowTenantSelectionGate = vi.fn();

vi.mock('@/lib/auth', () => ({
  shouldShowTenantSelectionGate: (pathname: string) => mockShouldShowTenantSelectionGate(pathname),
  getCurrentUser: () => ({ username: 'editor', email: null }),
  isSuperAdmin: () => false,
  logout: () => undefined,
}));

vi.mock('@/pages/tenant-select/TenantSelectPage', () => ({
  default: () => <div>tenant-gate</div>,
}));

vi.mock('@/pages/accept-invitation/AcceptInvitationPage', () => ({
  default: () => <div>accept-invitation</div>,
}));

vi.mock('@/components/layout/AppShell', async () => {
  const { Outlet } = await import('react-router-dom');
  return {
    AppShell: () => (
      <div>
        <div>app-shell</div>
        <Outlet />
      </div>
    ),
  };
});

vi.mock('@/pages/home/HomePage', () => ({
  default: () => <div>home-page</div>,
}));

vi.mock('@/pages/processes/ProcessesPage', () => ({
  default: () => <div>processes-page</div>,
}));

vi.mock('@/pages/tenants/TenantsPage', () => ({
  default: () => <div>tenants-page</div>,
}));

vi.mock('@/pages/process-model-detail/ProcessModelDetailPage', () => ({
  default: () => <div>process-model-detail-page</div>,
}));

function renderRoutes(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe('AppRoutes tenant gate', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('shows the landing gate when logged out and does not auto-redirect to Keycloak', () => {
    mockShouldShowTenantSelectionGate.mockReturnValue(true);

    renderRoutes('/');

    expect(screen.getByText('tenant-gate')).toBeInTheDocument();
    expect(screen.queryByText('home-page')).not.toBeInTheDocument();
    expect(screen.queryByText('Redirecting to sign in...')).not.toBeInTheDocument();
  });

  it('renders the app shell when the tenant cookie gate is not shown', () => {
    mockShouldShowTenantSelectionGate.mockReturnValue(false);

    renderRoutes('/');

    expect(screen.getByText('app-shell')).toBeInTheDocument();
    expect(screen.getByText('home-page')).toBeInTheDocument();
    expect(screen.queryByText('tenant-gate')).not.toBeInTheDocument();
  });

  it('re-opens the gate on /tenant', () => {
    mockShouldShowTenantSelectionGate.mockReturnValue(true);

    renderRoutes('/tenant');

    expect(screen.getByText('tenant-gate')).toBeInTheDocument();
    expect(screen.queryByText('home-page')).not.toBeInTheDocument();
  });

  it('does not intercept /accept-invitation', () => {
    mockShouldShowTenantSelectionGate.mockReturnValue(true);

    renderRoutes('/accept-invitation');

    expect(screen.getByText('accept-invitation')).toBeInTheDocument();
    expect(screen.queryByText('tenant-gate')).not.toBeInTheDocument();
    expect(mockShouldShowTenantSelectionGate).not.toHaveBeenCalled();
  });

  it('renders the tenants registry when the gate is not shown', async () => {
    mockShouldShowTenantSelectionGate.mockReturnValue(false);

    renderRoutes('/tenants');

    expect(screen.getByText('app-shell')).toBeInTheDocument();
    expect(await screen.findByText('tenants-page')).toBeInTheDocument();
  });
});
