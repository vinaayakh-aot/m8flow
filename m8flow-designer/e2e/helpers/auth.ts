import { expect, type Page } from '@playwright/test';

export type DesignerPersona = {
  username: string;
  password: string;
};

export function editorCredentials(): DesignerPersona {
  return {
    username: process.env.M8FLOW_E2E_EDITOR_USERNAME ?? 'editor',
    password: process.env.M8FLOW_E2E_EDITOR_PASSWORD ?? 'editor',
  };
}

export function superAdminCredentials(): DesignerPersona {
  return {
    username: process.env.M8FLOW_E2E_SUPER_ADMIN_USERNAME ?? 'super-admin',
    password: process.env.M8FLOW_E2E_SUPER_ADMIN_PASSWORD ?? 'super-admin',
  };
}

export function integratorCredentials(): DesignerPersona {
  return {
    username: process.env.M8FLOW_E2E_INTEGRATOR_USERNAME ?? 'integrator',
    password: process.env.M8FLOW_E2E_INTEGRATOR_PASSWORD ?? 'integrator',
  };
}

export const SELECTED_TENANT_COOKIE = 'm8flow_selected_tenant';

function isDesignerOrigin(url: URL): boolean {
  return url.origin.includes('localhost:6853');
}

/** Clear app cookies so each journey starts unauthenticated. */
export async function clearDesignerSession(page: Page): Promise<void> {
  await page.context().clearCookies();
}

export async function cookieValue(page: Page, name: string): Promise<string | undefined> {
  const fromDocument = await page.evaluate((cookieName) => {
    const match = document.cookie
      .split('; ')
      .find((entry) => entry.startsWith(`${cookieName}=`));
    return match ? decodeURIComponent(match.slice(cookieName.length + 1)) : '';
  }, name);
  if (fromDocument) {
    return fromDocument;
  }
  const cookies = await page.context().cookies();
  return cookies.find((cookie) => cookie.name === name)?.value;
}

export async function expectTwoButtonLanding(page: Page, timeout = 20_000): Promise<void> {
  await expect(page.getByTestId('shared-realm-sign-in-button')).toBeVisible({ timeout });
  await expect(page.getByTestId('global-admin-sign-in-button')).toBeVisible({ timeout });
}

/** Keycloak hosted login must collect username and password on one page. */
export async function expectCombinedKeycloakLoginPage(page: Page): Promise<void> {
  await expect(page.locator('#username')).toBeVisible();
  await expect(page.locator('#password')).toBeVisible();
  await expect(page.locator('#kc-login')).toBeVisible();
}

async function fillKeycloakCredentials(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await expectCombinedKeycloakLoginPage(page);
  await page.locator('#username').fill(persona.username);
  await page.locator('#password').fill(persona.password);
  await page.locator('#kc-login').click();
}

/** Seed users may still have Keycloak UPDATE_PASSWORD from the realm import. */
async function completeKeycloakUpdatePasswordIfShown(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  const heading = page.getByRole('heading', { name: 'Update password', exact: true });
  if (!(await heading.isVisible())) {
    return;
  }
  await page.getByRole('textbox', { name: 'New Password' }).fill(persona.password);
  await page.getByRole('textbox', { name: 'Confirm password' }).fill(persona.password);
  await page.getByRole('button', { name: 'Submit' }).click();
}

async function waitForDesignerOrigin(page: Page): Promise<void> {
  await page.waitForURL((url) => isDesignerOrigin(url), { timeout: 60_000 });
}

async function waitAfterKeycloakCredentials(page: Page, persona: DesignerPersona): Promise<void> {
  const updatePassword = page.getByRole('heading', { name: 'Update password', exact: true });
  await Promise.race([
    page.waitForURL((url) => isDesignerOrigin(url), { timeout: 60_000 }),
    updatePassword.waitFor({ state: 'visible', timeout: 60_000 }),
  ]);
  await completeKeycloakUpdatePasswordIfShown(page, persona);
  await waitForDesignerOrigin(page);
}

/**
 * Shared-realm sign-in through Keycloak, stopping once the browser is back
 * on designer. Callers assert Home, the tenant picker, or the zero-org gate.
 */
export async function signInAtSharedRealm(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await clearDesignerSession(page);
  await page.goto('/');
  await page.getByTestId('shared-realm-sign-in-button').click();
  await page.waitForURL(/\/realms\/m8flow\//, { timeout: 30_000 });
  await fillKeycloakCredentials(page, persona);
  await waitAfterKeycloakCredentials(page, persona);
}

/**
 * Shared-realm sign-in: designer landing → Sign In → Keycloak m8flow realm,
 * then tenant finalization and Home.
 */
export async function signInAsSharedRealmUser(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await signInAtSharedRealm(page, persona);
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({
    timeout: 60_000,
  });
}

/**
 * Platform admin sign-in: designer landing → Platform Admin Sign In →
 * master realm credentials → designer Home.
 */
export async function signInAsPlatformAdmin(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await clearDesignerSession(page);
  await page.goto('/');
  await page.getByTestId('global-admin-sign-in-button').click();
  await page.waitForURL(/\/realms\/master\//, { timeout: 30_000 });
  await fillKeycloakCredentials(page, persona);
  await waitAfterKeycloakCredentials(page, persona);
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible({
    timeout: 60_000,
  });
}

export async function logOutFromDesigner(page: Page): Promise<void> {
  await openProfileMenu(page);
  await page.getByRole('menuitem', { name: 'Log out' }).click();
  // Logout hops through backend + Keycloak; current designer URL already
  // matches origin 6853, so wait on the landing, not waitForURL.
  await expectTwoButtonLanding(page, 60_000);
}

export async function openProfileMenu(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Profile' }).click();
  await expect(page.getByRole('menu', { name: 'Profile' })).toBeVisible();
}

/**
 * Super-admin-only sidebar tenant filter (Sidebar.tsx's `showTenantSelector`).
 * `label` is the tenant's display name as shown in the `<option>` (e.g.
 * `'m8flow'`), not its id — the option value isn't guaranteed to match.
 */
export async function selectSidebarTenant(page: Page, label: string): Promise<void> {
  await page.getByRole('combobox', { name: /Tenant/ }).selectOption({ label });
}
