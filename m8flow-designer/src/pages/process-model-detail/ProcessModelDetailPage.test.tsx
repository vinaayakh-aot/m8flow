import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import ProcessModelDetailPage from './ProcessModelDetailPage';

const DETAIL = {
  id: 'finance/invoice-approval',
  display_name: 'Invoice Approval',
  description: 'Two-step',
  group_id: 'finance',
  group_display_name: 'Finance',
  last_run_in_seconds: 1_700_000_000,
  running_now: 1,
  runs_30d: 2,
  recent_instances: [],
  files: [],
};

function renderDetail(context: AppShellOutletContext, path = '/processes/finance:invoice-approval') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="/processes/:processModelId" element={<ProcessModelDetailPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProcessModelDetailPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('prompts super-admin when All Tenants is selected and does not fetch', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    renderDetail({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: true,
    });

    expect(screen.getByText('Choose a tenant')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('lets a non-admin editor open a model using the tenant cookie', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...DETAIL,
          recent_instances: [
            {
              id: 1042,
              started_by: 'editor',
              start_in_seconds: 1_700_000_000,
              duration_seconds: 102,
              status: 'complete',
            },
          ],
          files: [
            {
              name: 'invoice-approval.bpmn',
              size_bytes: 24576,
              updated_at_in_seconds: 1_700_000_000,
              primary: true,
            },
          ],
        }),
      }),
    );

    renderDetail({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: false,
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Invoice Approval' })).toBeInTheDocument();
    });
    expect(screen.getByTestId('process-model-detail')).toBeInTheDocument();
    expect(screen.getByText('Median time')).toBeInTheDocument();
    expect(screen.getByText('Errors 30d')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start process' })).toBeDisabled();
    expect(screen.getByRole('link', { name: /Open in modeler/ })).toHaveAttribute(
      'href',
      '/processes/finance:invoice-approval/modeler/invoice-approval.bpmn',
    );

    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain('/v1.0/m8flow/process-models/finance:invoice-approval');
    expect(url).not.toContain('tenantId=');

    fireEvent.click(screen.getByRole('button', { name: 'Start process' }));
    expect(vi.mocked(fetch).mock.calls).toHaveLength(1);
  });

  it('fetches detail for a concrete tenant and shows the display name', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => DETAIL,
      }),
    );

    renderDetail({
      scopedTenantId: 't1',
      selectedTenantId: 't1',
      isSuperAdmin: true,
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Invoice Approval' })).toBeInTheDocument();
    });
    expect(screen.getByTestId('process-model-detail')).toBeInTheDocument();
    expect(screen.getByText('Two-step')).toBeInTheDocument();
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain('/v1.0/m8flow/process-models/finance:invoice-approval');
    expect(url).toContain('tenantId=t1');
  });

  it('shows not found when the API returns 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ error_code: 'not_found' }),
      }),
    );

    renderDetail({
      scopedTenantId: 't1',
      selectedTenantId: 't1',
      isSuperAdmin: false,
    });

    await waitFor(() => {
      expect(screen.getByText('Process model not found.')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('process-model-detail')).not.toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({}),
      }),
    );

    renderDetail({
      scopedTenantId: null,
      selectedTenantId: null,
      isSuperAdmin: false,
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert').textContent).toMatch(/failed: 500/i);
  });
});
