import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import ProcessesPage from './ProcessesPage';

function renderWithOutlet(context: AppShellOutletContext, initial = '/processes') {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="/processes" element={<ProcessesPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProcessesPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('prompts super-admin when All Tenants is selected', () => {
    renderWithOutlet({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: true,
    });
    expect(screen.getByText('Choose a tenant')).toBeInTheDocument();
  });

  it('fetches and renders models for a concrete tenant', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: 'finance/invoice-approval',
            display_name: 'Invoice Approval',
            group_id: 'finance',
            group_display_name: 'Finance',
            last_run_in_seconds: null,
            runs_30d: 0,
          },
        ],
      }),
    );

    renderWithOutlet({
      scopedTenantId: 't1',
      selectedTenantId: 't1',
      isSuperAdmin: true,
    });

    await waitFor(() => {
      expect(screen.getByText('Invoice Approval')).toBeInTheDocument();
    });
    expect(fetch).toHaveBeenCalled();
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain('/v1.0/m8flow/process-models');
    expect(url).toContain('tenantId=t1');
  });

  function stubOneModel() {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          {
            id: 'finance/invoice-approval',
            display_name: 'Invoice Approval',
            group_id: 'finance',
            group_display_name: 'Finance',
            last_run_in_seconds: null,
            runs_30d: 0,
          },
        ],
      }),
    );
  }

  it('hides Start for users who cannot manage processes', async () => {
    stubOneModel();
    renderWithOutlet({
      scopedTenantId: 't1',
      selectedTenantId: 't1',
      isSuperAdmin: false,
      canManageProcesses: false,
    });
    await waitFor(() => expect(screen.getByText('Invoice Approval')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
    // The overflow menu also offers no Delete for these users.
    fireEvent.click(screen.getByRole('button', { name: 'More actions' }));
    expect(screen.queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument();
  });

  it('shows Start for users who can manage processes', async () => {
    stubOneModel();
    renderWithOutlet({
      scopedTenantId: 't1',
      selectedTenantId: 't1',
      isSuperAdmin: false,
      canManageProcesses: true,
    });
    await waitFor(() => expect(screen.getByText('Invoice Approval')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
  });

  it('opens the groups picker and applies a group filter', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: RequestInfo) => {
        const url = String(input);
        if (url.includes('/v1.0/m8flow/process-groups')) {
          return {
            ok: true,
            json: async () => [
              {
                id: 'finance',
                display_name: 'Finance',
                description: 'Invoice approvals',
                model_count: 1,
                last_run_in_seconds: null,
              },
            ],
          };
        }
        return {
          ok: true,
          json: async () => [
            {
              id: 'finance/invoice-approval',
              display_name: 'Invoice Approval',
              group_id: 'finance',
              group_display_name: 'Finance',
              last_run_in_seconds: null,
              runs_30d: 0,
            },
          ],
        };
      }),
    );

    renderWithOutlet(
      {
        scopedTenantId: 't1',
        selectedTenantId: 't1',
        isSuperAdmin: true,
      },
      '/processes',
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Approval')).toBeInTheDocument();
    });

    // "Browse groups" was removed; the "Showing [scope]" pill opens the picker.
    fireEvent.click(screen.getByRole('button', { name: /All groups/ }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: 'Process groups' })).toBeInTheDocument();
    });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/v1.0/m8flow/process-groups'),
      expect.anything(),
    );

    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /Finance/ }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clear' })).toBeInTheDocument();
  });
});
