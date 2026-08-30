import { fireEvent, render, screen } from '@testing-library/react';
import { forwardRef, useImperativeHandle, type Ref } from 'react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AppShellOutletContext } from '@/components/layout/AppShell';
import type { DiagramCanvasHandle } from './components/DiagramCanvasHandle';

vi.mock('./components/DiagramCanvas', () => ({
  DiagramCanvas: forwardRef(function DiagramCanvasStub(
    { xml, onDirtyChange }: { xml: string; onDirtyChange?: (dirty: boolean) => void },
    ref: Ref<DiagramCanvasHandle>,
  ) {
    useImperativeHandle(ref, () => ({
      saveXML: async () => xml,
      markSaved: () => onDirtyChange?.(false),
    }));
    return (
      <div>
        <button type="button" onClick={() => onDirtyChange?.(true)}>
          Mark dirty
        </button>
        canvas-ready
      </div>
    );
  }),
}));

import ProcessModelModelerPage from './ProcessModelModelerPage';

const FILE_XML = '<bpmn:definitions />';
const DETAIL = {
  id: 'finance/invoice-approval',
  display_name: 'Invoice Approval',
  description: '',
  group_id: 'finance',
  group_display_name: 'Finance',
  last_run_in_seconds: null,
  running_now: 0,
  runs_30d: 0,
  recent_instances: [],
  files: [
    {
      name: 'invoice-approval.bpmn',
      size_bytes: 24,
      updated_at_in_seconds: 1_700_000_000,
      primary: true,
    },
    {
      name: 'notes.md',
      size_bytes: 12,
      updated_at_in_seconds: 1_700_000_000,
      primary: false,
    },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

function stubFetch(detail = DETAIL) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    if (url.includes('/files/') && method === 'GET') {
      return { ok: true, status: 200, text: async () => FILE_XML, json: async () => ({}) };
    }
    if (url.includes('/files/') && method === 'DELETE') {
      return jsonResponse({});
    }
    if (url.includes('/files') && method === 'POST') {
      return jsonResponse({ name: 'extra.bpmn', size_bytes: 1, updated_at_in_seconds: 1 });
    }
    if (url.includes('/connectors-grouped')) {
      return jsonResponse([]);
    }
    if (url.includes('/process-models/finance:invoice-approval') && method === 'PUT') {
      return jsonResponse({
        id: detail.id,
        display_name: detail.display_name,
        description: detail.description,
        group_id: detail.group_id,
        group_display_name: detail.group_display_name,
      });
    }
    if (url.includes('/process-models/finance:invoice-approval')) {
      return jsonResponse(detail);
    }
    if (url.includes('/process-models')) {
      return jsonResponse([]);
    }
    return jsonResponse({});
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function renderModeler(
  context: AppShellOutletContext,
  path = '/processes/finance:invoice-approval/modeler/invoice-approval.bpmn',
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Outlet context={context} />}>
          <Route
            path="/processes/:processModelId/modeler/:fileName"
            element={<ProcessModelModelerPage />}
          />
          <Route path="/processes/:processModelId" element={<p>overview</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

const EDITOR_CONTEXT: AppShellOutletContext = {
  scopedTenantId: null,
  selectedTenantId: null,
  isSuperAdmin: false,
  canManageProcesses: true,
};

describe('ProcessModelModelerPage file chrome', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('hides delete and set-as-primary on the primary BPMN and shows View XML', async () => {
    stubFetch();
    renderModeler(EDITOR_CONTEXT);

    expect(await screen.findByText('canvas-ready')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View XML' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New file' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Set as primary' })).not.toBeInTheDocument();
  });

  it('deletes a non-primary file after confirm and returns to the overview', async () => {
    stubFetch();
    renderModeler(EDITOR_CONTEXT, '/processes/finance:invoice-approval/modeler/notes.md');

    expect(await screen.findByText('canvas-ready')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('heading', { name: 'Delete file' })).toBeInTheDocument();
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    expect(await screen.findByText('overview')).toBeInTheDocument();
  });

  it('opens View XML with the current file contents', async () => {
    stubFetch();
    renderModeler(EDITOR_CONTEXT);

    expect(await screen.findByText('canvas-ready')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View XML' }));
    expect(await screen.findByText(FILE_XML)).toBeInTheDocument();
  });

  it('warns before leaving when the file is dirty', async () => {
    stubFetch();
    renderModeler(EDITOR_CONTEXT);

    expect(await screen.findByText('canvas-ready')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mark dirty' }));
    fireEvent.click(screen.getByRole('link', { name: 'Process Groups' }));

    expect(await screen.findByRole('heading', { name: 'Unsaved changes' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Stay' }));
    expect(screen.getByText('canvas-ready')).toBeInTheDocument();
  });

  it('hides mutating chrome for a viewer', async () => {
    stubFetch();
    renderModeler({ ...EDITOR_CONTEXT, canManageProcesses: false });

    expect(await screen.findByText('canvas-ready')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'New file' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
  });

  it('shows Delete for a file that is not yet in the known list', async () => {
    stubFetch();
    renderModeler(EDITOR_CONTEXT, '/processes/finance:invoice-approval/modeler/just-added.md');

    expect(await screen.findByText('canvas-ready')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });
});
