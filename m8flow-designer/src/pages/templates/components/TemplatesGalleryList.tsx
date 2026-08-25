import { useEffect, useRef, type KeyboardEvent } from 'react';
import { ChevronLeft, ChevronRight, Download, FileText, Plus, Search, Trash2, Upload } from 'lucide-react';

import type { Template, TemplateVisibility } from '@/lib/templatesApi';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { formatRelativeTime } from '@/lib/relativeTime';
import { cn } from '@/lib/utils';

export type VisibilityFilter = TemplateVisibility | 'ALL';

export type TemplatesGalleryListProps = {
  templates: Template[];
  loading?: boolean;
  error?: string | null;
  search: string;
  onSearchChange: (value: string) => void;
  visibility: VisibilityFilter;
  onVisibilityChange: (value: VisibilityFilter) => void;
  order: 'asc' | 'desc';
  onToggleOrder: () => void;
  page: number;
  pageCount: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  onOpenTemplate?: (template: Template) => void;
  /** Opens the create-process-model-from-template dialog. Only enabled for
   * published templates when the caller isn't a super-admin (see this
   * component's own doc comment). */
  onUseTemplate?: (template: Template) => void;
  onExportTemplate?: (template: Template) => void;
  onDeleteTemplate?: (template: Template) => void;
  onImportClick?: () => void;
  /** Gates "Use template"/delete/import: every template-mutating backend
   * route unconditionally 403s for super-admin identities
   * (`TemplateService`'s own `is_super_admin_request()` guard, checked
   * regardless of tenant selection) — disabled here rather than letting
   * the action fail every time. */
  isSuperAdmin?: boolean;
};

const VISIBILITY_OPTIONS: { value: VisibilityFilter; label: string }[] = [
  { value: 'ALL', label: 'All visibility' },
  { value: 'PRIVATE', label: 'Private' },
  { value: 'TENANT', label: 'Tenant' },
  { value: 'PUBLIC', label: 'Public' },
];

/**
 * Templates gallery — search/filter/sort/paginate over
 * `GET /v1.0/m8flow/templates`, matching this app's own Processes-list
 * conventions (`ProcessesModelsList.tsx`) rather than porting
 * `m8flow-frontend`'s Carbon-based `TemplateGalleryPage`. Presentational:
 * the parent (`TemplatesPage`) owns fetching and filter state.
 */
export function TemplatesGalleryList({
  templates,
  loading = false,
  error = null,
  search,
  onSearchChange,
  visibility,
  onVisibilityChange,
  order,
  onToggleOrder,
  page,
  pageCount,
  totalCount,
  onPageChange,
  onOpenTemplate,
  onUseTemplate,
  onExportTemplate,
  onDeleteTemplate,
  onImportClick,
  isSuperAdmin = false,
}: TemplatesGalleryListProps) {
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      onSearchChange('');
      searchRef.current?.blur();
    }
  }

  const isEmpty = !loading && !error && templates.length === 0;
  const resultCount = `${totalCount} template${totalCount === 1 ? '' : 's'}`;

  return (
    <>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-[32px] font-semibold tracking-tight text-foreground">Templates</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            type="button"
            variant="pill-outline"
            size="pill"
            onClick={onImportClick}
            disabled={isSuperAdmin}
            title={isSuperAdmin ? 'Not available to super-admin' : undefined}
            className="gap-1.5"
          >
            <Upload className="size-3.5" strokeWidth={2.2} />
            Import
          </Button>
          {/* Blank-template creation deliberately out of scope for this
              ticket (no starter-BPMN precedent exists elsewhere in this
              app — "New process model" is the same kind of still-inert
              chrome on ProcessesModelsList). Not converted to Button. */}
          <button
            type="button"
            aria-disabled="true"
            title="Not yet available — use Import or create a template from an existing process model"
            className="inline-flex cursor-default items-center gap-2 rounded-full bg-nav-active px-5 py-2.5 text-[12.5px] font-semibold tracking-[0.04em] text-foreground uppercase shadow-xs select-none"
          >
            <Plus className="size-[15px]" strokeWidth={2.2} />
            New template
          </button>
        </div>
      </div>

      <div className="pb-14">
        <div className="mb-[18px] flex flex-wrap items-center gap-2.5">
          <label className="flex max-w-[420px] min-w-0 flex-1 items-center gap-2.5 rounded-full border border-border bg-card px-4 py-2.5">
            <Search className="size-4 shrink-0 text-muted-foreground" strokeWidth={2} />
            <Input
              ref={searchRef}
              type="search"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              onKeyDown={onSearchKeyDown}
              placeholder="Search templates"
              className="h-auto min-w-0 flex-1 border-none bg-transparent p-0 text-[13.5px] text-foreground shadow-none outline-none focus-visible:ring-0"
              aria-label="Search templates"
            />
            <kbd className="shrink-0 rounded-md border border-border px-1.5 py-px font-mono text-[11px] text-muted-foreground">
              ⌘K
            </kbd>
          </label>

          <label className="relative">
            <span className="sr-only">Visibility</span>
            <select
              value={visibility}
              onChange={(e) => onVisibilityChange(e.target.value as VisibilityFilter)}
              className="appearance-none rounded-full border border-border bg-card py-2 pr-8 pl-3.5 text-[13px] font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-nav-active/40"
            >
              {VISIBILITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={onToggleOrder}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-2 text-[13px] font-medium text-foreground"
            aria-label={`Sort by last updated, currently ${order === 'desc' ? 'newest first' : 'oldest first'}`}
          >
            Sort: updated {order === 'desc' ? '↓' : '↑'}
          </button>

          <div className="ml-auto whitespace-nowrap text-[13px] text-muted-foreground">
            {loading ? 'Loading…' : resultCount}
          </div>
        </div>

        {error ? (
          <p className="mb-4 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="py-8 text-sm text-muted-foreground" aria-busy="true">
            Loading templates…
          </p>
        ) : null}

        {isEmpty ? (
          <Card variant="bordered" className="px-6 py-[52px] text-center">
            <div className="text-[15.5px] font-semibold text-foreground">No templates found</div>
            <p className="mt-2 text-[13.5px] text-muted-foreground">
              {search.trim() || visibility !== 'ALL'
                ? 'Try a different search or clear the filters.'
                : 'No templates are available for this tenant yet.'}
            </p>
          </Card>
        ) : null}

        {!loading && templates.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {templates.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                isSuperAdmin={isSuperAdmin}
                onOpen={() => onOpenTemplate?.(template)}
                onUse={() => onUseTemplate?.(template)}
                onExport={() => onExportTemplate?.(template)}
                onDelete={() => onDeleteTemplate?.(template)}
              />
            ))}
          </div>
        ) : null}

        {!loading && !isEmpty ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-[13px] text-muted-foreground">
            <span>{resultCount}</span>
            <span className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                aria-label="Previous page"
                className="flex size-7 items-center justify-center rounded-full border border-border disabled:opacity-40"
              >
                <ChevronLeft className="size-3.5" />
              </button>
              <span className="font-mono">
                Page {page} of {Math.max(pageCount, 1)}
              </span>
              <button
                type="button"
                onClick={() => onPageChange(page + 1)}
                disabled={page >= pageCount}
                aria-label="Next page"
                className="flex size-7 items-center justify-center rounded-full border border-border disabled:opacity-40"
              >
                <ChevronRight className="size-3.5" />
              </button>
            </span>
          </div>
        ) : null}
      </div>
    </>
  );
}

function TemplateCard({
  template,
  isSuperAdmin,
  onOpen,
  onUse,
  onExport,
  onDelete,
}: {
  template: Template;
  isSuperAdmin: boolean;
  onOpen: () => void;
  onUse: () => void;
  onExport: () => void;
  onDelete: () => void;
}) {
  // "Use template" (create-process-model-from-template) is real, but
  // gated: the backend only accepts *published* templates
  // (`TemplateService.create_process_model_from_template`'s own
  // `is_published` check, a 400 otherwise) and unconditionally forbids
  // super-admin identities (see this file's own `isSuperAdmin` doc
  // comment) — disabled with an explanatory title in either case rather
  // than left to fail server-side every time.
  const useDisabled = !template.isPublished || isSuperAdmin;
  const useTitle = isSuperAdmin
    ? 'Not available to super-admin'
    : !template.isPublished
      ? 'Only published templates can be used to create a process model'
      : undefined;

  return (
    <Card
      variant="bordered"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen();
        }
      }}
      className="flex cursor-pointer flex-col gap-3 p-5"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="line-clamp-1 text-[14.5px] font-semibold text-foreground">{template.name}</div>
          <div className="mt-0.5 font-mono text-[11.5px] text-muted-foreground">
            {template.templateKey} · v{template.version}
          </div>
        </div>
        <Badge variant={template.isPublished ? 'success' : 'outline'} className="shrink-0">
          {template.isPublished ? 'Published' : 'Draft'}
        </Badge>
      </div>

      {template.description ? (
        <p className="line-clamp-2 text-[13px] text-muted-foreground">{template.description}</p>
      ) : (
        <p className="text-[13px] text-muted-foreground italic">No description</p>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="secondary">{template.visibility}</Badge>
        {template.category ? <Badge variant="outline">{template.category}</Badge> : null}
        {(template.tags ?? []).slice(0, 2).map((tag) => (
          <Badge key={tag} variant="ghost">
            {tag}
          </Badge>
        ))}
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-border pt-3 text-[12px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <FileText className="size-3.5" strokeWidth={1.8} />
          {template.files.length} file{template.files.length === 1 ? '' : 's'}
        </span>
        <span>Updated {formatRelativeTime(template.updatedAtInSeconds)}</span>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <Button type="button" variant="pill-outline" size="pill" onClick={onOpen} className="px-3.5 py-1.5 text-[11.5px]">
          Open
        </Button>
        <button
          type="button"
          aria-disabled={useDisabled}
          title={useTitle}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!useDisabled) onUse();
          }}
          className={cn(
            'inline-flex items-center rounded-full px-3.5 py-1.5 text-[11.5px] font-semibold tracking-[0.04em] uppercase select-none',
            'border border-border',
            useDisabled ? 'cursor-default text-muted-foreground' : 'cursor-pointer text-foreground hover:bg-muted',
          )}
        >
          Use template
        </button>
        <span className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onExport();
            }}
            title="Export as zip"
            aria-label="Export template"
            className="flex size-7 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Download className="size-3.5" strokeWidth={1.8} />
          </button>
          <button
            type="button"
            aria-disabled={isSuperAdmin}
            title={isSuperAdmin ? 'Not available to super-admin' : 'Delete template'}
            aria-label="Delete template"
            onClick={(e) => {
              e.stopPropagation();
              if (!isSuperAdmin) onDelete();
            }}
            className={cn(
              'flex size-7 items-center justify-center rounded-full',
              isSuperAdmin
                ? 'cursor-default text-muted-foreground/50'
                : 'cursor-pointer text-muted-foreground hover:bg-destructive/10 hover:text-destructive',
            )}
          >
            <Trash2 className="size-3.5" strokeWidth={1.8} />
          </button>
        </span>
      </div>
    </Card>
  );
}
