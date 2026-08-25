import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  ensureSelectedTenantCookie,
  getAccessToken,
  getCurrentUser,
  getSelectedTenantId,
  isLoggedIn,
  isSuperAdmin,
  login,
  logout,
} from './auth';

const NOW_MS = 1_700_000_000_000;
const BACKEND_BASE_URL =
  (import.meta.env.VITE_BACKEND_BASE_URL as string | undefined) ?? 'http://localhost:6840';

function encodeJwt(
  payload: Record<string, unknown>,
  options: { urlSafe?: boolean } = {},
): string {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }));
  let body = btoa(JSON.stringify(payload));
  if (options.urlSafe) {
    body = body.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  return `${header}.${body}.signature`;
}

function clearCookies(): void {
  for (const cookie of document.cookie.split(';')) {
    const name = cookie.split('=')[0]?.trim();
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    }
  }
}

function setCookies(cookies: Record<string, string>): void {
  clearCookies();
  for (const [name, value] of Object.entries(cookies)) {
    document.cookie = `${name}=${value}`;
  }
}

function stubLocation(href: string): { href: string; origin: string } {
  const url = new URL(href);
  const location = {
    href: url.toString(),
    origin: url.origin,
  };
  vi.stubGlobal('location', location);
  return location;
}

describe('auth', () => {
  afterEach(() => {
    clearCookies();
    sessionStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe('getAccessToken', () => {
    it('returns null when the access_token cookie is missing', () => {
      setCookies({ id_token: 'ignored' });
      expect(getAccessToken()).toBeNull();
    });

    it('returns the decoded access_token cookie value, including JWT padding', () => {
      const token = encodeJwt({ sub: 'user-1' });
      setCookies({ access_token: encodeURIComponent(token) });
      expect(getAccessToken()).toBe(token);
    });
  });

  describe('isLoggedIn', () => {
    it.each([
      ['no access_token cookie', {}, false],
      ['empty access_token cookie', { access_token: '' }, false],
    ] as const)('returns false when %s', (_label, cookies, expected) => {
      setCookies(cookies);
      expect(isLoggedIn()).toBe(expected);
    });

    it.each([
      ['in the past', Math.floor(NOW_MS / 1000) - 60, false],
      ['exactly now', Math.floor(NOW_MS / 1000), false],
      ['in the future', Math.floor(NOW_MS / 1000) + 60, true],
    ] as const)('uses exp %s relative to Date.now()', (_label, exp, expected) => {
      vi.spyOn(Date, 'now').mockReturnValue(NOW_MS);
      setCookies({ access_token: encodeURIComponent(encodeJwt({ exp })) });
      expect(isLoggedIn()).toBe(expected);
    });

    it.each([
      ['missing', {}],
      ['a string', { exp: '9999999999' }],
    ] as const)('returns true when exp is %s', (_label, extra) => {
      vi.spyOn(Date, 'now').mockReturnValue(NOW_MS);
      setCookies({ access_token: encodeURIComponent(encodeJwt(extra)) });
      expect(isLoggedIn()).toBe(true);
    });

    it('treats a present undecodable access_token as logged in because expiry cannot be read', () => {
      setCookies({ access_token: 'not-a-jwt' });
      expect(isLoggedIn()).toBe(true);
      expect(getCurrentUser()).toBeNull();
    });
  });

  describe('getCurrentUser', () => {
    it('returns null when neither id_token nor access_token is present', () => {
      expect(getCurrentUser()).toBeNull();
    });

    it('returns null when the chosen token cannot be decoded', () => {
      setCookies({ id_token: 'not-a-jwt' });
      expect(getCurrentUser()).toBeNull();
    });

    it('prefers id_token claims over access_token claims', () => {
      setCookies({
        id_token: encodeURIComponent(
          encodeJwt({ preferred_username: 'from-id', email: 'id@example.com' }),
        ),
        access_token: encodeURIComponent(
          encodeJwt({ preferred_username: 'from-access', email: 'access@example.com' }),
        ),
      });
      expect(getCurrentUser()).toEqual({
        username: 'from-id',
        email: 'id@example.com',
      });
    });

    it('falls back to access_token when id_token is absent', () => {
      setCookies({
        access_token: encodeURIComponent(
          encodeJwt({ preferred_username: 'from-access', email: 'access@example.com' }),
        ),
      });
      expect(getCurrentUser()).toEqual({
        username: 'from-access',
        email: 'access@example.com',
      });
    });

    it('decodes URL-safe base64 JWT payloads', () => {
      setCookies({
        id_token: encodeURIComponent(
          encodeJwt({ preferred_username: 'editor', email: 'editor@example.com' }, { urlSafe: true }),
        ),
      });
      expect(getCurrentUser()).toEqual({
        username: 'editor',
        email: 'editor@example.com',
      });
    });

    it.each([
      [
        'string claims',
        { preferred_username: 'editor', email: 'editor@example.com' },
        { username: 'editor', email: 'editor@example.com' },
      ],
      [
        'non-string claims',
        { preferred_username: 12, email: ['editor@example.com'] },
        { username: null, email: null },
      ],
      [
        'mixed string username and non-string email',
        { preferred_username: 'editor', email: 1 },
        { username: 'editor', email: null },
      ],
      [
        'empty-string username as a string claim, not null',
        { preferred_username: '', email: 'editor@example.com' },
        { username: '', email: 'editor@example.com' },
      ],
    ] as const)('maps %s', (_label, payload, expected) => {
      setCookies({ id_token: encodeURIComponent(encodeJwt({ ...payload })) });
      expect(getCurrentUser()).toEqual(expected);
    });
  });

  describe('login', () => {
    it('sends the browser to the backend login route with the encoded current href', () => {
      const currentHref = 'http://localhost:6853/home?tab=design&x=1';
      stubLocation(currentHref);

      login();

      expect(window.location.href).toBe(
        `${BACKEND_BASE_URL}/v1.0/login?redirect_url=${encodeURIComponent(currentHref)}`,
      );
    });

    it('passes authentication_identifier=master for platform admin sign-in', async () => {
      const { loginAsPlatformAdmin } = await import('./auth');
      stubLocation('http://localhost:6853/');

      loginAsPlatformAdmin();

      expect(window.location.href).toBe(
        `${BACKEND_BASE_URL}/v1.0/login?redirect_url=${encodeURIComponent('http://localhost:6853/')}&authentication_identifier=master`,
      );
    });

    it('passes prompt=login when requested', () => {
      stubLocation('http://localhost:6853/');

      login({ promptLogin: true });

      expect(window.location.href).toBe(
        `${BACKEND_BASE_URL}/v1.0/login?redirect_url=${encodeURIComponent('http://localhost:6853/')}&prompt=login`,
      );
    });

    it('consumes the post-logout prompt flag set by logout()', async () => {
      const { resumeLoginAfterLogout } = await import('./auth');
      sessionStorage.setItem('m8flow_post_logout_prompt', '1');
      sessionStorage.setItem('m8flow_last_auth_realm', 'master');
      stubLocation('http://localhost:6853/');

      resumeLoginAfterLogout();

      expect(window.location.href).toBe(
        `${BACKEND_BASE_URL}/v1.0/login?redirect_url=${encodeURIComponent('http://localhost:6853/')}&authentication_identifier=master&prompt=login`,
      );
      expect(sessionStorage.getItem('m8flow_post_logout_prompt')).toBeNull();
    });
  });

  describe('logout', () => {
    it('sends the browser to the backend logout route with origin, id_token, and auth realm', () => {
      const idToken = encodeJwt({ preferred_username: 'editor' });
      setCookies({ id_token: idToken, authentication_identifier: 'm8flow' });
      stubLocation('http://localhost:6853/home?tab=design');

      logout();

      const expected = new URLSearchParams({
        redirect_url: 'http://localhost:6853/',
        id_token: idToken,
        authentication_identifier: 'm8flow',
      });
      expect(window.location.href).toBe(`${BACKEND_BASE_URL}/v1.0/logout?${expected.toString()}`);
      expect(sessionStorage.getItem('m8flow_post_logout_prompt')).toBe('1');
      expect(sessionStorage.getItem('m8flow_last_auth_realm')).toBe('m8flow');
    });

    it('sends an empty id_token query param when the id_token cookie is missing', () => {
      stubLocation('http://localhost:6853/home?tab=design');

      logout();

      const expected = new URLSearchParams({
        redirect_url: 'http://localhost:6853/',
        id_token: '',
      });
      expect(window.location.href).toBe(`${BACKEND_BASE_URL}/v1.0/logout?${expected.toString()}`);
    });

    it('does not substitute access_token when id_token is missing', () => {
      setCookies({ access_token: 'access-only-token' });
      stubLocation('http://localhost:6853/home?tab=design');

      logout();

      const expected = new URLSearchParams({
        redirect_url: 'http://localhost:6853/',
        id_token: '',
      });
      expect(window.location.href).toBe(`${BACKEND_BASE_URL}/v1.0/logout?${expected.toString()}`);
    });
  });

  describe('ensureSelectedTenantCookie', () => {
    it('sets m8flow_selected_tenant from the JWT m8flow_tenant_id claim', () => {
      const token = encodeJwt({ m8flow_tenant_id: 'tenant-uuid-1', preferred_username: 'editor' });
      setCookies({ access_token: token });

      ensureSelectedTenantCookie();

      expect(getSelectedTenantId()).toBe('tenant-uuid-1');
    });

    it('does not overwrite an existing selected-tenant cookie', () => {
      setCookies({
        m8flow_selected_tenant: 'already-set',
        access_token: encodeJwt({ m8flow_tenant_id: 'other' }),
      });

      ensureSelectedTenantCookie();

      expect(getSelectedTenantId()).toBe('already-set');
    });
  });

  describe('isSuperAdmin', () => {
    it('returns false when no tokens are present', () => {
      expect(isSuperAdmin()).toBe(false);
    });

    it('detects a top-level roles claim on the access_token', () => {
      setCookies({
        access_token: encodeURIComponent(encodeJwt({ roles: ['super-admin'] })),
      });
      expect(isSuperAdmin()).toBe(true);
    });

    it('detects a groups claim ending with :super-admin', () => {
      setCookies({
        access_token: encodeURIComponent(encodeJwt({ groups: ['/t1:super-admin'] })),
      });
      expect(isSuperAdmin()).toBe(true);
    });

    it('detects realm_access.roles', () => {
      setCookies({
        id_token: encodeURIComponent(
          encodeJwt({ realm_access: { roles: ['super-admin'] } }),
        ),
      });
      expect(isSuperAdmin()).toBe(true);
    });

    it('returns false for a regular editor token', () => {
      setCookies({
        access_token: encodeURIComponent(
          encodeJwt({ roles: ['t1:editor'], groups: ['t1:editor'] }),
        ),
      });
      expect(isSuperAdmin()).toBe(false);
    });
  });
});
