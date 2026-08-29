import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import AuthenticationsPage from './AuthenticationsPage';

const mockFetchAuthentications = vi.fn();
const mockCreateAuthentication = vi.fn();
const mockRevokeAuthentication = vi.fn();

vi.mock('@/lib/authenticationsApi', async () => {
  const actual = await vi.importActual<typeof import('@/lib/authenticationsApi')>(
    '@/lib/authenticationsApi',
  );
  return {
    ...actual,
    fetchAuthentications: (...args: unknown[]) => mockFetchAuthentications(...args),
    createAuthentication: (...args: unknown[]) => mockCreateAuthentication(...args),
    revokeAuthentication: (...args: unknown[]) => mockRevokeAuthentication(...args),
  };
});

function renderWithOutlet(context: AppShellOutletContext) {
  return render(
    <MemoryRouter initialEntries={['/authentications']}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="/authentications" element={<AuthenticationsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

const ACCOUNT = {
  id: 7,
  name: 'ci-bot',
  client_id: 'aabbccdd',
  created_at_in_seconds: Math.floor(Date.now() / 1000) - 120,
  created_by_user_id: 1,
};

describe('AuthenticationsPage', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('hides manage actions and explains denial when the role cannot read', () => {
    renderWithOutlet({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: false,
      canReadAuthentications: false,
      canManageAuthentications: false,
    });
    expect(screen.getByText('Not available')).toBeInTheDocument();
    expect(mockFetchAuthentications).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /New service account/i })).not.toBeInTheDocument();
  });

  it('prompts super-admin when All Tenants is selected', () => {
    renderWithOutlet({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: true,
      canReadAuthentications: true,
      canManageAuthentications: true,
    });
    expect(screen.getByText('Choose a tenant')).toBeInTheDocument();
    expect(mockFetchAuthentications).not.toHaveBeenCalled();
  });

  it('lists accounts for a viewer without create or revoke', async () => {
    mockFetchAuthentications.mockResolvedValue([ACCOUNT]);
    renderWithOutlet({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: false,
      canReadAuthentications: true,
      canManageAuthentications: false,
    });

    expect(await screen.findByText('ci-bot')).toBeInTheDocument();
    expect(screen.getByText('aabbccdd')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /New service account/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Revoke' })).not.toBeInTheDocument();
  });

  it('creates an account and shows the secret once', async () => {
    mockFetchAuthentications.mockResolvedValue([]);
    mockCreateAuthentication.mockResolvedValue({
      ...ACCOUNT,
      api_key: 'm8sa_aabbccdd.secret-once',
    });

    renderWithOutlet({
      scopedTenantId: 't1',
      selectedTenantId: 't1',
      isSuperAdmin: true,
      canReadAuthentications: true,
      canManageAuthentications: true,
    });

    fireEvent.click(await screen.findByRole('button', { name: /New service account/i }));
    fireEvent.change(screen.getByTestId('authentication-name'), { target: { value: 'ci-bot' } });
    fireEvent.click(screen.getByTestId('authentication-create'));

    expect(await screen.findByTestId('authentication-api-key')).toHaveTextContent(
      'm8sa_aabbccdd.secret-once',
    );
    expect(mockCreateAuthentication).toHaveBeenCalledWith('ci-bot', 't1');

    fireEvent.click(screen.getByTestId('authentication-secret-done'));
    await waitFor(() => {
      expect(screen.queryByTestId('authentication-api-key')).not.toBeInTheDocument();
    });
  });

  it('revokes after confirm', async () => {
    mockFetchAuthentications.mockResolvedValue([ACCOUNT]);
    mockRevokeAuthentication.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithOutlet({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: false,
      canReadAuthentications: true,
      canManageAuthentications: true,
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Revoke' }));
    await waitFor(() => {
      expect(mockRevokeAuthentication).toHaveBeenCalledWith(7, null);
    });
  });
});
