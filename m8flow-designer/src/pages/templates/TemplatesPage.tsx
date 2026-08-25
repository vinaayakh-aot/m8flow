import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';

import {
  deleteTemplate,
  exportTemplate,
  fetchTemplates,
  type Template,
  type TemplatePagination,
} from '@/lib/templatesApi';
import { downloadBlob } from '@/lib/download';
import type { AppShellOutletContext } from '@/components/layout/AppShell';
import { Card } from '@/components/ui/card';
import { CreateProcessModelFromTemplateDialog } from './components/CreateProcessModelFromTemplateDialog';
import { ImportTemplateDialog } from './components/ImportTemplateDialog';
import { TemplatesGalleryList, type VisibilityFilter } from './components/TemplatesGalleryList';

const PER_PAGE = 12;
/** Matches ProcessesModelsList's own ⌘K-search debounce intent — avoids
 * firing a server request per keystroke (this list is server-paginated/
 * -searched, unlike Processes' client-side filter, so debouncing here is
 * load-bearing, not just cosmetic). */
const SEARCH_DEBOUNCE_MS = 300;

/**
 * Templates gallery — wired to GET /v1.0/m8flow/templates (Template
 * modeler map, ticket 02 — .scratch/template-modeler/). Same tenant-gating
 * posture as ProcessesPage: super-admin must pick a concrete tenant, no
 * merged all-tenant catalog view, even though the backend itself would
 * technically allow one for an unscoped super-admin request — kept
 * consistent with this app's own established tenant-isolation convention
 * rather than relying on that backend leniency.
 */
export default function TemplatesPage() {
  const { scopedTenantId, isSuperAdmin } = useOutletContext<AppShellOutletContext>();
  const navigate = useNavigate();
  const needsTenant = isSuperAdmin && !scopedTenantId;

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [visibility, setVisibility] = useState<VisibilityFilter>('ALL');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);

  const [templates, setTemplates] = useState<Template[]>([]);
  const [pagination, setPagination] = useState<TemplatePagination | null>(null);
  const [loading, setLoading] = useState(!needsTenant);
  const [error, setError] = useState<string | null>(null);
  // Bumped after a successful delete/import to trigger a refetch — a
  // dependency, not a direct re-call, since the main fetch effect below
  // already owns loading/error state for the current filter combination.
  const [reloadKey, setReloadKey] = useState(0);
  // Ticket 04 (create/import/export/delete): errors from these actions are
  // reported separately from the list's own load `error` above, so a
  // failed delete doesn't get mistaken for "the list failed to load."
  const [actionError, setActionError] = useState<string | null>(null);
  const [useTemplateTarget, setUseTemplateTarget] = useState<Template | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  // Debounce the raw input into the value that actually drives the fetch,
  // and reset to page 1 whenever the effective search term changes.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [visibility, order]);

  useEffect(() => {
    if (needsTenant) {
      setTemplates([]);
      setPagination(null);
      setLoading(false);
      setError(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTemplates({
      search: search || undefined,
      visibility: visibility === 'ALL' ? undefined : visibility,
      sortBy: 'created',
      order,
      page,
      perPage: PER_PAGE,
      tenantId: scopedTenantId ?? undefined,
    })
      .then(({ results, pagination: pg }) => {
        if (!cancelled) {
          setTemplates(results);
          setPagination(pg);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load templates');
          setTemplates([]);
          setPagination(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [needsTenant, scopedTenantId, search, visibility, order, page, reloadKey]);

  const handleExport = useCallback(async (template: Template) => {
    setActionError(null);
    try {
      const blob = await exportTemplate(template.id);
      downloadBlob(`${template.templateKey}-v${template.version}.zip`, blob);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to export template');
    }
  }, []);

  const handleDelete = useCallback(async (template: Template) => {
    // Native confirm, not a custom dialog — no mockup/prior pattern in this
    // app for a delete-confirmation modal, and this is a single yes/no
    // gate on an otherwise real, working action (see ticket 04's notes).
    if (!window.confirm(`Delete "${template.name}"? This cannot be undone.`)) {
      return;
    }
    setActionError(null);
    try {
      await deleteTemplate(template.id);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete template');
    }
  }, []);

  if (needsTenant) {
    return (
      <main className="flex-1 px-11 py-10">
        <div className="mb-7">
          <h1 className="font-display text-[32px] font-semibold tracking-tight">Templates</h1>
        </div>
        <Card variant="bordered" className="max-w-lg p-6">
          <p className="text-[15px] font-semibold text-foreground">Choose a tenant</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Templates are tenant-scoped. Select a concrete tenant in the sidebar — All
            Tenants is not supported on Templates.
          </p>
        </Card>
      </main>
    );
  }

  const pageCount = pagination ? Math.max(pagination.pages, 1) : 1;

  return (
    <main className="flex-1 px-11 py-10">
      {actionError ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {actionError}
        </p>
      ) : null}
      <TemplatesGalleryList
        templates={templates}
        loading={loading}
        error={error}
        search={searchInput}
        onSearchChange={setSearchInput}
        visibility={visibility}
        onVisibilityChange={setVisibility}
        order={order}
        onToggleOrder={() => setOrder((o) => (o === 'desc' ? 'asc' : 'desc'))}
        page={page}
        pageCount={pageCount}
        totalCount={pagination?.total ?? templates.length}
        onPageChange={(next) => setPage(Math.min(Math.max(next, 1), pageCount))}
        onOpenTemplate={(template) => navigate(`/templates/${template.id}`)}
        onUseTemplate={setUseTemplateTarget}
        onExportTemplate={handleExport}
        onDeleteTemplate={handleDelete}
        onImportClick={() => setImportOpen(true)}
        isSuperAdmin={isSuperAdmin}
      />

      {useTemplateTarget ? (
        <CreateProcessModelFromTemplateDialog
          template={useTemplateTarget}
          open
          onClose={() => setUseTemplateTarget(null)}
          scopedTenantId={scopedTenantId}
          onCreated={(encodedProcessModelId) => {
            setUseTemplateTarget(null);
            navigate(`/processes/${encodedProcessModelId}`);
          }}
        />
      ) : null}

      <ImportTemplateDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={(templateId) => {
          setImportOpen(false);
          navigate(`/templates/${templateId}`);
        }}
      />
    </main>
  );
}
