import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { GLOBAL_TENANT_STORAGE_KEY } from '@/lib/selectedTenant';
import { AppShell } from './AppShell';

const mockGetCurrentUser = vi.fn();
const mockLogout = vi.fn();
const mockIsSuperAdmin = vi.fn();
const mockFetchTenants = vi.fn().mockResolvedValue([]);

vi.mock('@/lib/auth', () => ({
  getCurrentUser: () => mockGetCurrentUser(),
  isSuperAdmin: () => mockIsSuperAdmin(),
  logout: () => mockLogout(),
}));

const mockFetchCapabilities = vi.fn().mockResolvedValue({
  can_manage_processes: false,
  can_read_authentications: false,
  can_manage_authentications: false,
});

vi.mock('@/lib/api', () => ({
  fetchTenants: (...args: unknown[]) => mockFetchTenants(...args),
  fetchCapabilities: () => mockFetchCapabilities(),
}));

function renderShell(initialPath = '/') {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <AppShell />,
        children: [
          { index: true, element: <div>home-outlet</div> },
          { path: 'processes', element: <div>processes-outlet</div> },
          {
            path: 'processes/:processModelId',
            element: <div>detail-outlet</div>,
          },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  );
  return render(<RouterProvider router={router} />);
}

describe('AppShell', () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockIsSuperAdmin.mockReturnValue(false);
    mockFetchCapabilities.mockResolvedValue({
      can_manage_processes: false,
      can_read_authentications: false,
      can_manage_authentications: false,
    });
    try {
      localStorage.clear();
    } catch {
      /* ignore */
    }
  });

  it.each([
    [
      'username when both username and email are present',
      { username: 'editor', email: 'editor@example.com' },
      'editor',
    ],
    ['email when username is null', { username: null, email: 'editor@example.com' }, 'editor@example.com'],
    ['unknown user when both claims are null', { username: null, email: null }, 'unknown user'],
    ['unknown user when getCurrentUser returns null', null, 'unknown user'],
    [
      'empty username rather than falling through to email (nullish coalescing)',
      { username: '', email: 'editor@example.com' },
      '',
    ],
  ] as const)('shows %s in the Profile menu', (_label, user, displayed) => {
    mockGetCurrentUser.mockReturnValue(user);

    renderShell();

    fireEvent.click(screen.getByRole('button', { name: 'Profile' }));
    const identity = screen.getByRole('menu', { name: 'Profile' }).querySelector('strong');
    expect(identity).not.toBeNull();
    expect(identity?.textContent).toBe(displayed);
  });

  it('for a non-admin editor: no Tenant selector and does not fetch tenants', () => {
    mockGetCurrentUser.mockReturnValue({ username: 'editor', email: null });
    mockIsSuperAdmin.mockReturnValue(false);

    renderShell();

    expect(screen.getByText('flow', { exact: false })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Processes' })).toBeInTheDocument();
    expect(screen.getByText('Process Instances')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(mockFetchTenants).not.toHaveBeenCalled();
    expect(screen.getByText('home-outlet')).toBeInTheDocument();
  });

  it('shows Setup → Authentications when capabilities allow read', async () => {
    mockGetCurrentUser.mockReturnValue({ username: 'integrator', email: null });
    mockFetchCapabilities.mockResolvedValue({
      can_manage_processes: false,
      can_read_authentications: true,
      can_manage_authentications: true,
    });

    renderShell();

    expect(await screen.findByRole('link', { name: 'Authentications' })).toHaveAttribute(
      'href',
      '/authentications',
    );
  });

  it('for a super-admin: shows Tenant selector and fetches tenants', () => {
    mockGetCurrentUser.mockReturnValue({ username: 'super-admin', email: null });
    mockIsSuperAdmin.mockReturnValue(true);
    mockFetchTenants.mockResolvedValue([{ id: 't1', name: 'Tenant One' }]);

    renderShell();

    expect(screen.getByRole('combobox', { name: /Tenant/ })).toBeInTheDocument();
    expect(mockFetchTenants).toHaveBeenCalled();
  });

  it('restores the persisted tenant on refresh', () => {
    localStorage.setItem(GLOBAL_TENANT_STORAGE_KEY, 't1');
    mockGetCurrentUser.mockReturnValue({ username: 'super-admin', email: null });
    mockIsSuperAdmin.mockReturnValue(true);
    mockFetchTenants.mockResolvedValue([{ id: 't1', name: 'Tenant One' }]);

    renderShell();

    expect(screen.getByRole('combobox', { name: /Tenant/ })).toHaveValue('t1');
  });

  it('persists tenant changes and clears All Tenants', async () => {
    mockGetCurrentUser.mockReturnValue({ username: 'super-admin', email: null });
    mockIsSuperAdmin.mockReturnValue(true);
    mockFetchTenants.mockResolvedValue([{ id: 't1', name: 'Tenant One' }]);

    renderShell();

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Tenant One' })).toBeInTheDocument();
    });

    const select = screen.getByRole('combobox', { name: /Tenant/ });
    fireEvent.change(select, { target: { value: 't1' } });
    expect(localStorage.getItem(GLOBAL_TENANT_STORAGE_KEY)).toBe('t1');

    fireEvent.change(select, { target: { value: '' } });
    expect(localStorage.getItem(GLOBAL_TENANT_STORAGE_KEY)).toBeNull();
    expect(select).toHaveValue('');
  });

  it('calls logout from the Profile popout menu', () => {
    mockGetCurrentUser.mockReturnValue({ username: 'editor', email: null });

    renderShell();
    fireEvent.click(screen.getByRole('button', { name: 'Profile' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Log out' }));

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('marks Processes active on /processes and keeps Home as a live link', () => {
    mockGetCurrentUser.mockReturnValue({ username: 'editor', email: null });

    renderShell('/processes');

    expect(screen.getByRole('link', { name: 'Processes' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current');
    expect(screen.getByText('processes-outlet')).toBeInTheDocument();
  });
});
