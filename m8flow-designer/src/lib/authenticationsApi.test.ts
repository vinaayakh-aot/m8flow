import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getAccessToken, resumeLoginAfterLogout } = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
  resumeLoginAfterLogout: vi.fn(),
}));

vi.mock('./auth', () => ({
  getAccessToken,
  resumeLoginAfterLogout,
}));

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
  statusText: ok ? 'OK' : 'Error',
  json: vi.fn().mockResolvedValue(body ?? {}),
  clone: vi.fn().mockReturnThis(),
  text: vi.fn().mockResolvedValue(JSON.stringify(body ?? {})),
});

describe('authenticationsApi', () => {
  beforeEach(() => {
    vi.resetModules();
    getAccessToken.mockReset().mockReturnValue('access-token');
    resumeLoginAfterLogout.mockReset();
    vi.unstubAllGlobals();
  });

  it('lists accounts and appends tenantId for super-admin scope', async () => {
    const { fetchAuthentications } = await import('./authenticationsApi');
    const fetchMock = vi.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        body: [{ id: 1, name: 'ci-bot', client_id: 'abc', created_at_in_seconds: 1, created_by_user_id: 2 }],
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const rows = await fetchAuthentications('t1');
    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('ci-bot');
    expect(String(fetchMock.mock.calls[0][0])).toContain('/v1.0/authentications?tenantId=t1');
  });

  it('creates an account and returns the one-time api_key', async () => {
    const { createAuthentication } = await import('./authenticationsApi');
    const fetchMock = vi.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 201,
        body: {
          id: 1,
          name: 'ci-bot',
          client_id: 'abc',
          created_at_in_seconds: 1,
          created_by_user_id: 2,
          api_key: 'm8sa_abc.secret',
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const created = await createAuthentication('ci-bot');
    expect(created.api_key).toBe('m8sa_abc.secret');
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({ method: 'POST' }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({ name: 'ci-bot' });
  });

  it('revokes by id', async () => {
    const { revokeAuthentication } = await import('./authenticationsApi');
    const fetchMock = vi.fn().mockResolvedValue(makeResponse({ ok: true, status: 200, body: { ok: true } }));
    vi.stubGlobal('fetch', fetchMock);

    await revokeAuthentication(9, 't2');
    expect(String(fetchMock.mock.calls[0][0])).toContain('/v1.0/authentications/9?tenantId=t2');
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ method: 'DELETE' }));
  });
});
