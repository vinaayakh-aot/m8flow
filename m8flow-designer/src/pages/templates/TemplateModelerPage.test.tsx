import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TemplateModelerPage from './TemplateModelerPage';

// Same constraint ProcessModelModelerPage.tsx documents in App.tsx (bpmn-js's
// raw ESM doesn't resolve under Vitest's Node-based SSR module runner) — and
// the same reason that page has no test file of its own. These tests only
// exercise the states that never reach <DiagramCanvas> (invalid id, 404,
// fetch error, no-diagram-file), which is real, valuable coverage on its own
// and matches this app's existing precedent rather than fighting the
// library's ESM resolution in a unit test.
function renderAt(templateId: string) {
  return render(
    <MemoryRouter initialEntries={[`/templates/${templateId}`]}>
      <Routes>
        <Route path="/templates/:templateId" element={<TemplateModelerPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TemplateModelerPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows "Template not found" for a non-numeric id without fetching', () => {
    renderAt('not-a-number');
    expect(screen.getByText('Template not found.')).toBeInTheDocument();
  });

  it('shows "Template not found" when the backend 404s', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }));

    renderAt('999');

    await waitFor(() => {
      expect(screen.getByText('Template not found.')).toBeInTheDocument();
    });
  });

  it('shows a visible error for a non-404 fetch failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    renderAt('7');

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('GET');
    });
  });

  it('shows an explicit error when the template has no BPMN/DMN file', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          id: 3,
          templateKey: 'docs-only',
          version: '1',
          name: 'Docs Only Template',
          description: null,
          tags: null,
          category: null,
          tenantId: 't1',
          visibility: 'TENANT',
          files: [{ fileType: 'md', fileName: 'README.md' }],
          isPublished: false,
          status: 'draft',
          createdBy: 'editor',
          modifiedBy: 'editor',
          createdAtInSeconds: 1_700_000_000,
          updatedAtInSeconds: 1_700_000_000,
        }),
      }),
    );

    renderAt('3');

    await waitFor(() => {
      expect(
        screen.getByText('This template has no BPMN or DMN file to open in the modeler.'),
      ).toBeInTheDocument();
    });
  });
});
