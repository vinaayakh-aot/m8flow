import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import TenantsPage from './TenantsPage';

const mockFetchTenants = vi.fn();
const mockCreateTenant = vi.fn();
const mockUpdateTenantName = vi.fn();
const mockRefreshTenants = vi.fn();
const mockFetchTenantMembers = vi.fn();
const mockFetchTenantGroups = vi.fn();
const mockFetchTenantInvitations = vi.fn();
const mockGetSelectedTenantId = vi.fn((): string | null => null);

vi.mock('@/lib/tenantsApi', async () => {
  const actual = await vi.importActual<typeof import('@/lib/tenantsApi')>('@/lib/tenantsApi');
  return {
    ...actual,
    fetchTenants: (...args: unknown[]) => mockFetchTenants(...args),
    createTenant: (...args: unknown[]) => mockCreateTenant(...args),
    updateTenantName: (...args: unknown[]) => mockUpdateTenantName(...args),
  };
});

vi.mock('@/lib/tenantAdminApi', async () => {
  const actual = await vi.importActual<typeof import('@/lib/tenantAdminApi')>(
    '@/lib/tenantAdminApi',
  );
  return {
    ...actual,
    fetchTenantMembers: (...args: unknown[]) => mockFetchTenantMembers(...args),
    fetchTenantGroups: (...args: unknown[]) => mockFetchTenantGroups(...args),
  };
});

vi.mock('@/lib/invitationManagementApi', async () => {
  const actual = await vi.importActual<typeof import('@/lib/invitationManagementApi')>(
    '@/lib/invitationManagementApi',
  );
  return {
    ...actual,
    fetchTenantInvitations: (...args: unknown[]) => mockFetchTenantInvitations(...args),
  };
});

vi.mock('@/lib/auth', async () => {
  const actual = await vi.importActual<typeof import('@/lib/auth')>('@/lib/auth');
  return {
    ...actual,
    getSelectedTenantId: () => mockGetSelectedTenantId(),
  };
});

function renderWithOutlet(context: Partial<AppShellOutletContext> = {}) {
  const full: AppShellOutletContext = {
    scopedTenantId: null,
    selectedTenantId: null,
    isSuperAdmin: true,
    refreshTenants: mockRefreshTenants,
    ...context,
  };
  return render(
    <MemoryRouter initialEntries={['/tenants']}>
      <Routes>
        <Route element={<Outlet context={full} />}>
          <Route path="/tenants" element={<TenantsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

const ACME = { id: 't1', name: 'Acme Corp', slug: 'acme-corp', status: 'ACTIVE' as const };
const BETA = { id: 't2', name: 'Beta Labs', slug: 'beta-labs', status: 'INACTIVE' as const };

describe('TenantsPage', () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockGetSelectedTenantId.mockReturnValue(null);
    mockFetchTenantMembers.mockResolvedValue({
      tenant_id: 't1',
      search: '',
      offset: 0,
      limit: 10,
      has_more: false,
      members: [
        {
          id: 'u1',
          username: 'editor',
          display_name: 'Ed Itor',
          roles: ['editor'],
          groups: [],
        },
      ],
    });
    mockFetchTenantGroups.mockResolvedValue({
      tenant_id: 't1',
      search: '',
      offset: 0,
      limit: 10,
      has_more: false,
      groups: [],
    });
    mockFetchTenantInvitations.mockResolvedValue({
      tenant_id: 't1',
      results: [],
      total: 0,
      offset: 0,
      limit: 100,
    });
  });

  it('explains denial and does not fetch for a non-super-admin', () => {
    renderWithOutlet({ isSuperAdmin: false });
    expect(screen.getByText('Not available')).toBeInTheDocument();
    expect(mockFetchTenants).not.toHaveBeenCalled();
    expect(screen.queryByTestId('tenant-add-button')).not.toBeInTheDocument();
  });

  it('lists tenants and filters by name, alias, and status', async () => {
    mockFetchTenants.mockResolvedValue([ACME, BETA]);
    renderWithOutlet();

    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Beta Labs')).toBeInTheDocument();
    expect(screen.getByText('Showing 2 of 2 tenants')).toBeInTheDocument();
    expect(screen.queryByTestId('tenant-member-add-button')).not.toBeInTheDocument();
    expect(screen.queryByTestId('tenant-accordion-details-t1')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('tenant-search-input'), { target: { value: 'acme' } });
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.queryByText('Beta Labs')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 1 of 2 tenants')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('tenant-search-input'), { target: { value: '' } });
    fireEvent.change(screen.getByTestId('tenant-search-type-select'), { target: { value: 'slug' } });
    fireEvent.change(screen.getByTestId('tenant-search-input'), { target: { value: 'beta-labs' } });
    expect(screen.getByText('Beta Labs')).toBeInTheDocument();
    expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('tenant-search-input'), { target: { value: '' } });
    fireEvent.change(screen.getByTestId('tenant-status-filter'), { target: { value: 'INACTIVE' } });
    expect(screen.getByText('Beta Labs')).toBeInTheDocument();
    expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument();
  });

  it('sorts by alias when the alias header is clicked', async () => {
    mockFetchTenants.mockResolvedValue([BETA, ACME]);
    renderWithOutlet();
    await screen.findByText('Acme Corp');

    fireEvent.click(screen.getByTestId('tenant-sort-slug'));
    fireEvent.click(screen.getByTestId('tenant-sort-slug'));
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('Beta Labs');
    expect(rows[1]).toHaveTextContent('Acme Corp');
  });

  it('creates a tenant from a name-only dialog', async () => {
    mockFetchTenants.mockResolvedValueOnce([]).mockResolvedValueOnce([ACME]);
    mockCreateTenant.mockResolvedValue(ACME);
    renderWithOutlet();

    fireEvent.click(await screen.findByTestId('tenant-add-button'));
    fireEvent.change(screen.getByTestId('tenant-name'), { target: { value: 'Acme Corp' } });
    fireEvent.click(screen.getByTestId('tenant-save'));

    await waitFor(() => {
      expect(mockCreateTenant).toHaveBeenCalledWith('Acme Corp', []);
    });
    expect(mockRefreshTenants).toHaveBeenCalled();
    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();
  });

  it('blocks a duplicate name before posting', async () => {
    mockFetchTenants.mockResolvedValue([ACME]);
    renderWithOutlet();

    fireEvent.click(await screen.findByTestId('tenant-add-button'));
    fireEvent.change(screen.getByTestId('tenant-name'), { target: { value: 'Acme Corp' } });
    fireEvent.click(screen.getByTestId('tenant-save'));

    expect(await screen.findByText('A tenant with this name already exists.')).toBeInTheDocument();
    expect(mockCreateTenant).not.toHaveBeenCalled();
  });

  it('renames via PUT name-only', async () => {
    mockFetchTenants.mockResolvedValueOnce([ACME]).mockResolvedValueOnce([
      { ...ACME, name: 'Acme Incorporated' },
    ]);
    mockUpdateTenantName.mockResolvedValue(undefined);
    renderWithOutlet();

    fireEvent.click(await screen.findByTestId('tenant-rename-t1'));
    fireEvent.change(screen.getByTestId('tenant-name'), { target: { value: 'Acme Incorporated' } });
    fireEvent.click(screen.getByTestId('tenant-save'));

    await waitFor(() => {
      expect(mockUpdateTenantName).toHaveBeenCalledWith('t1', 'Acme Incorporated');
    });
    expect(mockRefreshTenants).toHaveBeenCalled();
    expect(await screen.findByText('Acme Incorporated')).toBeInTheDocument();
  });

  it('expands a registry row into tenant admin for that tenant without setting the cookie', async () => {
    mockFetchTenants.mockResolvedValue([ACME, BETA]);
    renderWithOutlet({ isSuperAdmin: true, scopedTenantId: null, selectedTenantId: null });

    await screen.findByText('Acme Corp');
    expect(screen.queryByTestId('tenant-member-add-button')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tenant-accordion-toggle-t1'));

    expect(await screen.findByTestId('tenant-accordion-details-t1')).toBeInTheDocument();
    expect(await screen.findByText('Ed Itor')).toBeInTheDocument();
    expect(screen.getByTestId('tenant-member-add-button')).toBeInTheDocument();
    expect(screen.getByTestId('tenant-group-add-button')).toBeInTheDocument();
    expect(screen.getByTestId('tenant-invite-user-button')).toBeInTheDocument();
    expect(screen.getByTestId('pending-invitations-panel')).toBeInTheDocument();
    expect(mockFetchTenantMembers).toHaveBeenCalledWith('t1', expect.any(Object));
    expect(mockFetchTenantInvitations).toHaveBeenCalledWith('t1', { limit: 100 });
    expect(mockGetSelectedTenantId).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
  });

  it('keeps only one registry row expanded at a time', async () => {
    mockFetchTenants.mockResolvedValue([ACME, BETA]);
    mockFetchTenantMembers.mockImplementation((tenantId: string) =>
      Promise.resolve({
        tenant_id: tenantId,
        search: '',
        offset: 0,
        limit: 10,
        has_more: false,
        members: [
          {
            id: 'u1',
            username: 'editor',
            display_name: tenantId === 't2' ? 'Beta Editor' : 'Ed Itor',
            roles: ['editor'],
            groups: [],
          },
        ],
      }),
    );
    renderWithOutlet({ isSuperAdmin: true });

    await screen.findByText('Acme Corp');
    fireEvent.click(screen.getByTestId('tenant-accordion-toggle-t1'));
    expect(await screen.findByTestId('tenant-accordion-details-t1')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tenant-accordion-toggle-t2'));
    expect(await screen.findByTestId('tenant-accordion-details-t2')).toBeInTheDocument();
    expect(screen.queryByTestId('tenant-accordion-details-t1')).not.toBeInTheDocument();
    expect(mockFetchTenantMembers).toHaveBeenCalledWith('t2', expect.any(Object));
  });
});
