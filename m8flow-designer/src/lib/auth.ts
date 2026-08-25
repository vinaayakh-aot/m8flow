/**
 * Login for m8flow-designer piggybacks on the same backend-mediated Keycloak
 * flow m8flow-frontend uses (see UserService.ts there): the browser is sent to
 * the host backend's `/v1.0/login` route, which redirects to Keycloak's hosted
 * login page (the "Keycloak login page" referred to here — it is served by
 * Keycloak/the backend, not by any frontend React component). Keycloak then
 * redirects to the backend's `/v1.0/login_return`, which exchanges the code
 * for tokens and sets non-httpOnly `access_token` / `id_token` cookies on
 * this shared `localhost` host before finally redirecting back here.
 *
 * See m8flow_backend/routes/login_controller.py for the backend side.
 */

const BACKEND_BASE_URL: string =
  (import.meta.env.VITE_BACKEND_BASE_URL as string | undefined) ?? 'http://localhost:6840';

function readCookie(name: string): string | null {
  const match = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1];
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function tokenIsExpired(decoded: Record<string, unknown> | null): boolean {
  const exp = decoded?.exp;
  if (typeof exp !== 'number') {
    return false;
  }
  return exp * 1000 <= Date.now();
}

export function getAccessToken(): string | null {
  return readCookie('access_token');
}

export function isLoggedIn(): boolean {
  const token = getAccessToken();
  if (!token) {
    return false;
  }
  return !tokenIsExpired(decodeJwtPayload(token));
}

export function getCurrentUser(): { username: string | null; email: string | null } | null {
  const token = readCookie('id_token') ?? getAccessToken();
  if (!token) {
    return null;
  }
  const decoded = decodeJwtPayload(token);
  if (!decoded) {
    return null;
  }
  return {
    username: typeof decoded.preferred_username === 'string' ? decoded.preferred_username : null,
    email: typeof decoded.email === 'string' ? decoded.email : null,
  };
}

const SUPER_ADMIN_ROLE = 'super-admin';

function groupIndicatesSuperAdmin(group: string): boolean {
  const normalized = group.replace(/^\/+|\/+$/g, '').split('/').pop();
  return (
    normalized === SUPER_ADMIN_ROLE ||
    (normalized?.endsWith(`:${SUPER_ADMIN_ROLE}`) ?? false)
  );
}

function tokenIndicatesSuperAdmin(decoded: Record<string, unknown>): boolean {
  const roles = decoded.roles;
  if (Array.isArray(roles) && roles.includes(SUPER_ADMIN_ROLE)) {
    return true;
  }

  const groups = decoded.groups;
  if (Array.isArray(groups)) {
    for (const group of groups) {
      if (typeof group === 'string' && groupIndicatesSuperAdmin(group)) {
        return true;
      }
    }
  }

  const realmAccess = decoded.realm_access;
  if (realmAccess && typeof realmAccess === 'object') {
    const realmRoles = (realmAccess as Record<string, unknown>).roles;
    if (Array.isArray(realmRoles) && realmRoles.includes(SUPER_ADMIN_ROLE)) {
      return true;
    }
  }

  return false;
}

/**
 * Mirrors m8flow-frontend UserService.isSuperAdmin() — client-side JWT
 * heuristic only (ticket 02). Prefer access_token (Keycloak puts M8Flow
 * roles in a top-level `roles` claim there), fall back to id_token.
 */
export function isSuperAdmin(): boolean {
  for (const token of [getAccessToken(), readCookie('id_token')]) {
    const decoded = token ? decodeJwtPayload(token) : null;
    if (decoded && tokenIndicatesSuperAdmin(decoded)) {
      return true;
    }
  }
  return false;
}

const SELECTED_TENANT_COOKIE = 'm8flow_selected_tenant';

export function getSelectedTenantId(): string | null {
  return readCookie(SELECTED_TENANT_COOKIE);
}

/**
 * Home/backend routes require the `m8flow_selected_tenant` cookie (AGENTS.md).
 * Designer has no tenant-picker for regular users; when the cookie is missing,
 * finalize from the Keycloak JWT `m8flow_tenant_id` claim (same host cookie
 * pattern as m8flow-frontend's TenantSelectPage).
 */
export function ensureSelectedTenantCookie(): void {
  // Super-admins use optional tenant scope (All Tenants); do not invent a cookie
  // from a missing claim — Home APIs allow null scope for them.
  if (isSuperAdmin()) {
    return;
  }
  if (getSelectedTenantId()) {
    return;
  }
  for (const token of [getAccessToken(), readCookie('id_token')]) {
    const decoded = token ? decodeJwtPayload(token) : null;
    const tenantId = decoded?.m8flow_tenant_id;
    if (typeof tenantId === 'string' && tenantId.trim()) {
      document.cookie = `${SELECTED_TENANT_COOKIE}=${encodeURIComponent(tenantId.trim())}; Path=/; SameSite=Lax`;
      return;
    }
  }
}

const POST_LOGOUT_PROMPT_KEY = 'm8flow_post_logout_prompt';
const LAST_AUTH_REALM_KEY = 'm8flow_last_auth_realm';

function consumePostLogoutPrompt(): boolean {
  try {
    if (sessionStorage.getItem(POST_LOGOUT_PROMPT_KEY) !== '1') {
      return false;
    }
    sessionStorage.removeItem(POST_LOGOUT_PROMPT_KEY);
    return true;
  } catch {
    return false;
  }
}

/** Realm used for the previous session (set on logout so we resume the same Keycloak realm). */
export function getLastAuthRealm(): string | null {
  try {
    const value = sessionStorage.getItem(LAST_AUTH_REALM_KEY);
    return value && value.trim() ? value.trim() : null;
  } catch {
    return null;
  }
}

export function login(options?: {
  authenticationIdentifier?: string;
  /** Force Keycloak to show the credential form (no silent SSO). */
  promptLogin?: boolean;
}): void {
  const redirectUrl = window.location.href;
  const params = new URLSearchParams({
    redirect_url: redirectUrl,
  });
  const fromQuery = new URLSearchParams(window.location.search).get(
    'authentication_identifier',
  );
  const identifier = options?.authenticationIdentifier || fromQuery;
  if (identifier) {
    params.set('authentication_identifier', identifier);
  }
  // Always evaluate the post-logout flag (do not short-circuit) so it is cleared.
  const fromLogout = consumePostLogoutPrompt();
  if (options?.promptLogin || fromLogout) {
    params.set('prompt', 'login');
  }
  window.location.href = `${BACKEND_BASE_URL}/v1.0/login?${params.toString()}`;
}

/** Master-realm platform admin login (Keycloak `super-admin` role). */
export function loginAsPlatformAdmin(options?: { promptLogin?: boolean }): void {
  login({ authenticationIdentifier: 'master', promptLogin: options?.promptLogin });
}

/**
 * After logout / cold visit: resume the same realm as the last session when
 * known (so platform admins return to master), and always force the Keycloak
 * credential form so a leftover SSO cookie cannot skip the password prompt.
 */
export function resumeLoginAfterLogout(): void {
  const lastRealm = getLastAuthRealm();
  if (lastRealm === 'master') {
    loginAsPlatformAdmin({ promptLogin: true });
    return;
  }
  login({
    authenticationIdentifier: lastRealm || undefined,
    promptLogin: true,
  });
}

export function logout(): void {
  const idToken = readCookie('id_token') ?? '';
  const authId = readCookie('authentication_identifier') ?? '';
  try {
    sessionStorage.setItem(POST_LOGOUT_PROMPT_KEY, '1');
    if (authId) {
      sessionStorage.setItem(LAST_AUTH_REALM_KEY, authId);
    }
  } catch {
    // sessionStorage may be unavailable; logout still proceeds.
  }
  // Trailing slash so Keycloak's registered `http://localhost:6853/*`
  // post-logout URI matches (bare origin often fails "Invalid redirect uri").
  const redirectUrl = `${window.location.origin}/`;
  const params = new URLSearchParams({
    redirect_url: redirectUrl,
    id_token: idToken,
  });
  if (authId) {
    params.set('authentication_identifier', authId);
  }
  window.location.href = `${BACKEND_BASE_URL}/v1.0/logout?${params.toString()}`;
}
