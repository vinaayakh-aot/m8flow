import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import ProcessInstanceDetailPage from './ProcessInstanceDetailPage';

// Same constraint TemplateModelerPage.test.tsx/ProcessModelModelerPage
// document: bpmn-js's raw ESM doesn't resolve under Vitest's Node-based
// SSR module runner. These tests only exercise states that never reach
// the lazy-loaded <InstanceDiagramViewer> (invalid id, tenant gate, 404,
// fetch error, no-bpmn_xml) — real, valuable coverage on its own.
function renderWithOutlet(context: AppShellOutletContext, initial = '/process-instances/7') {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route path="/process-instances/:instanceId" element={<ProcessInstanceDetailPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function mockDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 7,
    process_model_identifier: 'finance/invoice-approval',
    process_model_display_name: 'Invoice Approval',
    status: 'waiting',
    started_by: 'editor',
    start_in_seconds: 1_700_000_000,
    end_in_seconds: null,
    bpmn_xml: null,
    tasks: [],
    ...overrides,
  };
}

describe('ProcessInstanceDetailPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows "not found" for a non-numeric id without fetching', () => {
    renderWithOutlet(
      { scopedTenantId: 't1', selectedTenantId: 't1', isSuperAdmin: false },
      '/process-instances/not-a-number',
    );
    expect(screen.getByText('Process instance not found.')).toBeInTheDocument();
  });

  it('prompts super-admin when All Tenants is selected', () => {
    renderWithOutlet({ scopedTenantId: null, selectedTenantId: null, isSuperAdmin: true });
    expect(
      screen.getByText('Process instances are tenant-scoped. Select a concrete tenant in the sidebar.'),
    ).toBeInTheDocument();
  });

  it('shows "not found" when the backend 404s', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    renderWithOutlet({ scopedTenantId: 't1', selectedTenantId: 't1', isSuperAdmin: false });

    await waitFor(() => {
      expect(screen.getByText('Process instance not found.')).toBeInTheDocument();
    });
  });

  it('shows a visible error for a non-404 fetch failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    renderWithOutlet({ scopedTenantId: 't1', selectedTenantId: 't1', isSuperAdmin: false });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows metadata and a fallback message when no bpmn_xml is available', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockDetail(),
      }),
    );

    renderWithOutlet({ scopedTenantId: 't1', selectedTenantId: 't1', isSuperAdmin: false });

    await waitFor(() => {
      expect(screen.getByText(/Invoice Approval/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Started by/)).toBeInTheDocument();
    expect(
      screen.getByText(
        'No BPMN diagram is available for this instance (its process definition may have been removed).',
      ),
    ).toBeInTheDocument();
    // Download is disabled with no bpmn_xml.
    expect(screen.getByRole('button', { name: /Download/ })).toBeDisabled();
  });
});
