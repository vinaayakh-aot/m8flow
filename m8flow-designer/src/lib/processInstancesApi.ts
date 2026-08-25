import { apiGet } from './api';

/**
 * Client for m8flow-backend's `/v1.0/m8flow/process-instances*` routes
 * (Process Instances + task-state map, ticket 02 —
 * `.scratch/process-instances-task-state/`, backend built in ticket 01).
 * Response shapes read directly from `process_instances_controller.py`/
 * `workflow.list_instances_for_designer`/`get_instance_detail_for_
 * designer`, snake_case (unlike Templates' camelCase) — same convention
 * as this app's other `/v1.0/m8flow/*` routes (`ProcessModelListItem`,
 * `HomeRecentInstance`, etc. in `lib/api.ts`).
 */

export type ProcessInstanceListItem = {
  id: number;
  process_model_identifier: string;
  process_model_display_name: string;
  status: string;
  started_by: string;
  start_in_seconds: number | null;
  end_in_seconds: number | null;
};

export type ProcessInstancePagination = {
  count: number;
  total: number;
  pages: number;
};

export type ProcessInstanceListResponse = {
  results: ProcessInstanceListItem[];
  pagination: ProcessInstancePagination;
};

/** Allowlisted server sort keys — must mirror workflow.py's
 * `_INSTANCE_SORTS`. Kept as a union so the UI's sort <select> can't emit
 * a value the backend would silently ignore. */
export type ProcessInstanceSort = 'newest' | 'oldest' | 'recent_start' | 'status';

export type ProcessInstanceListFilters = {
  status?: string;
  search?: string;
  /** Exact initiator-username match; options from fetchProcessInstanceOwners. */
  startedBy?: string;
  sort?: ProcessInstanceSort;
  page?: number;
  perPage?: number;
  /** Super-admin only; same convention as fetchProcessModels/fetchTemplates. */
  tenantId?: string | null;
};

export function processInstancesPath(filters: ProcessInstanceListFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.search) params.set('search', filters.search);
  if (filters.startedBy) params.set('started_by', filters.startedBy);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.page !== undefined) params.set('page', String(filters.page));
  if (filters.perPage !== undefined) params.set('per_page', String(filters.perPage));
  if (filters.tenantId) params.set('tenantId', filters.tenantId);
  const qs = params.toString();
  return qs ? `/v1.0/m8flow/process-instances?${qs}` : '/v1.0/m8flow/process-instances';
}

export function fetchProcessInstances(
  filters: ProcessInstanceListFilters = {},
): Promise<ProcessInstanceListResponse> {
  return apiGet<ProcessInstanceListResponse>(processInstancesPath(filters));
}

export type ProcessInstanceOwnersResponse = { owners: string[] };

export function processInstanceOwnersPath(tenantId?: string | null): string {
  const base = '/v1.0/m8flow/process-instances/owners';
  return tenantId ? `${base}?tenantId=${encodeURIComponent(tenantId)}` : base;
}

/** Distinct initiator usernames for the "started by" filter dropdown. */
export function fetchProcessInstanceOwners(tenantId?: string | null): Promise<string[]> {
  return apiGet<ProcessInstanceOwnersResponse>(processInstanceOwnersPath(tenantId)).then(
    (r) => r.owners ?? [],
  );
}

export type ProcessInstanceTaskState = {
  bpmn_identifier: string;
  state: string;
};

export type ProcessInstanceDetail = {
  id: number;
  process_model_identifier: string;
  process_model_display_name: string;
  status: string;
  started_by: string;
  start_in_seconds: number | null;
  end_in_seconds: number | null;
  bpmn_xml: string | null;
  tasks: ProcessInstanceTaskState[];
};

export function processInstanceDetailPath(id: number, tenantId?: string | null): string {
  const base = `/v1.0/m8flow/process-instances/${id}`;
  return tenantId ? `${base}?tenantId=${encodeURIComponent(tenantId)}` : base;
}

export function fetchProcessInstanceDetail(
  id: number,
  tenantId?: string | null,
): Promise<ProcessInstanceDetail> {
  return apiGet<ProcessInstanceDetail>(processInstanceDetailPath(id, tenantId));
}
