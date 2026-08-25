import { beforeEach, describe, expect, it, vi } from 'vitest';

const { ensureSelectedTenantCookie, getAccessToken, resumeLoginAfterLogout } = vi.hoisted(() => ({
  ensureSelectedTenantCookie: vi.fn(),
  getAccessToken: vi.fn(),
  resumeLoginAfterLogout: vi.fn(),
}));

vi.mock('./auth', () => ({
  ensureSelectedTenantCookie,
  getAccessToken,
  resumeLoginAfterLogout,
}));

import { homeStatsPath } from './api';

const makeResponse = ({
  ok,
  status,
  body,
}: {
  ok: boolean;
  status: number;
  body?: unknown;
}) => ({
  ok,
  status,
  statusText: ok ? 'OK' : 'Unauthorized',
  json: vi.fn().mockResolvedValue(body ?? {}),
  clone: vi.fn().mockReturnThis(),
  text: vi.fn().mockResolvedValue(typeof body === 'string' ? body : JSON.stringify(body ?? {})),
});

describe('apiGet auth-retry-on-401', () => {
  beforeEach(() => {
    // fetchWithAuthRetry's redirect-dedup flag is module-level state; reset
    // the module too so "already redirected" from one test can't suppress
    // the assertion in the next.
    vi.resetModules();
    ensureSelectedTenantCookie.mockReset();
    getAccessToken.mockReset().mockReturnValue('access-token');
    resumeLoginAfterLogout.mockReset();
    vi.unstubAllGlobals();
  });

  it('retries once after a silent refresh when the first request gets a 401', async () => {
    const { apiGet } = await import('./api');
    const fetchMock = vi
      .fn()
      // 1) original GET -> 401 (expired access token)
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }))
      // 2) POST /v1.0/refresh -> ok
      .mockResolvedValueOnce(makeResponse({ ok: true, status: 200 }))
      // 3) retried original GET -> success
      .mockResolvedValueOnce(makeResponse({ ok: true, status: 200, body: { id: 't1' } }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await apiGet('/v1.0/m8flow/process-models');

    expect(result).toEqual({ id: 't1' });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toEqual(expect.stringContaining('/v1.0/refresh'));
    expect(fetchMock.mock.calls[1][1]).toEqual(expect.objectContaining({ method: 'POST' }));
    expect(resumeLoginAfterLogout).not.toHaveBeenCalled();
  });

  it('deduplicates concurrent refreshes into a single /v1.0/refresh call', async () => {
    const { apiGet } = await import('./api');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }))
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }))
      .mockResolvedValueOnce(makeResponse({ ok: true, status: 200 }))
      .mockResolvedValueOnce(makeResponse({ ok: true, status: 200, body: { a: 1 } }))
      .mockResolvedValueOnce(makeResponse({ ok: true, status: 200, body: { b: 2 } }));
    vi.stubGlobal('fetch', fetchMock);

    const [a, b] = await Promise.all([
      apiGet('/v1.0/m8flow/process-models'),
      apiGet('/v1.0/m8flow/process-groups'),
    ]);

    expect(a).toEqual({ a: 1 });
    expect(b).toEqual({ b: 2 });
    const refreshCalls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).includes('/v1.0/refresh'),
    );
    expect(refreshCalls).toHaveLength(1);
  });

  it('redirects to login when the silent refresh itself fails', async () => {
    const { apiGet, ApiError } = await import('./api');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }))
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiGet('/v1.0/m8flow/process-models')).rejects.toBeInstanceOf(ApiError);
    expect(resumeLoginAfterLogout).toHaveBeenCalledTimes(1);
    // No point retrying the original request without a refreshed token.
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('redirects to login when a request is still unauthorized after a successful refresh', async () => {
    const { apiGet } = await import('./api');
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }))
      .mockResolvedValueOnce(makeResponse({ ok: true, status: 200 }))
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiGet('/v1.0/m8flow/process-models')).rejects.toThrow();
    expect(resumeLoginAfterLogout).toHaveBeenCalledTimes(1);
    // Original request, refresh, retried request — no infinite loop.
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('does not attempt a refresh for non-401 failures', async () => {
    const { apiGet, ApiError } = await import('./api');
    const fetchMock = vi.fn().mockResolvedValueOnce(makeResponse({ ok: false, status: 404 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiGet('/v1.0/m8flow/process-models')).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(resumeLoginAfterLogout).not.toHaveBeenCalled();
  });
});

describe('api helpers', () => {
  it('builds home-stats path without tenant when unset', () => {
    expect(homeStatsPath(null)).toBe('/v1.0/m8flow/home-stats');
    expect(homeStatsPath(undefined)).toBe('/v1.0/m8flow/home-stats');
  });

  it('appends tenantId when set', () => {
    expect(homeStatsPath('t2')).toBe('/v1.0/m8flow/home-stats?tenantId=t2');
  });
});

describe('homeRecentInstancesPath', () => {
  it('builds path with optional tenantId', async () => {
    const { homeRecentInstancesPath } = await import('./api');
    expect(homeRecentInstancesPath(null)).toBe('/v1.0/m8flow/home-recent-instances');
    expect(homeRecentInstancesPath('t2')).toBe(
      '/v1.0/m8flow/home-recent-instances?tenantId=t2',
    );
  });
});

describe('processModelsPath', () => {
  it('builds path with tenant and optional group', async () => {
    const { processModelsPath } = await import('./api');
    expect(processModelsPath(null)).toBe('/v1.0/m8flow/process-models');
    expect(processModelsPath('t1')).toBe(
      '/v1.0/m8flow/process-models?tenantId=t1',
    );
    expect(processModelsPath('t1', 'finance')).toBe(
      '/v1.0/m8flow/process-models?tenantId=t1&group=finance',
    );
  });
});

describe('processGroupsPath', () => {
  it('builds path with optional tenantId', async () => {
    const { processGroupsPath } = await import('./api');
    expect(processGroupsPath(null)).toBe('/v1.0/m8flow/process-groups');
    expect(processGroupsPath('t1')).toBe('/v1.0/m8flow/process-groups?tenantId=t1');
  });
});

describe('processModelDetailPath', () => {
  it('keeps colon separators and optional tenantId', async () => {
    const { processModelDetailPath } = await import('./api');
    expect(processModelDetailPath('finance:invoice-approval')).toBe(
      '/v1.0/m8flow/process-models/finance:invoice-approval',
    );
    expect(processModelDetailPath('finance:invoice-approval', 't1')).toBe(
      '/v1.0/m8flow/process-models/finance:invoice-approval?tenantId=t1',
    );
  });
});