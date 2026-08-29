import { apiFetch, apiGet, ApiError } from './api';

export type ServiceAccount = {
  id: number;
  name: string;
  client_id: string;
  created_at_in_seconds: number;
  created_by_user_id: number;
};

export type CreatedServiceAccount = ServiceAccount & {
  api_key: string;
};

function tenantQuery(tenantId: string | null | undefined): string {
  if (!tenantId) {
    return '';
  }
  return `?tenantId=${encodeURIComponent(tenantId)}`;
}

function listPath(tenantId: string | null | undefined): string {
  return `/v1.0/authentications${tenantQuery(tenantId)}`;
}

function itemPath(accountId: number, tenantId: string | null | undefined): string {
  return `/v1.0/authentications/${accountId}${tenantQuery(tenantId)}`;
}

export function authenticationsErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.serverMessage) {
    return error.serverMessage;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export async function fetchAuthentications(
  tenantId?: string | null,
): Promise<ServiceAccount[]> {
  const rows = await apiGet<unknown>(listPath(tenantId));
  return Array.isArray(rows) ? (rows as ServiceAccount[]) : [];
}

export async function createAuthentication(
  name: string,
  tenantId?: string | null,
): Promise<CreatedServiceAccount> {
  const response = await apiFetch(listPath(tenantId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ name }),
  });
  return (await response.json()) as CreatedServiceAccount;
}

export async function revokeAuthentication(
  accountId: number,
  tenantId?: string | null,
): Promise<void> {
  await apiFetch(itemPath(accountId, tenantId), { method: 'DELETE' });
}
