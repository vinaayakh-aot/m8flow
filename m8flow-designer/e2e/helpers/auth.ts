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

/** Clear app cookies so each journey starts unauthenticated. */
export async function clearDesignerSession(page: Page): Promise<void> {
  await page.context().clearCookies();
}

async function fillKeycloakCredentials(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await expect(page.locator('#username')).toBeVisible();
  await expect(page.locator('#password')).toBeVisible();
  await page.locator('#username').fill(persona.username);
  await page.locator('#password').fill(persona.password);
  await page.locator('#kc-login').click();
}

/**
 * Shared-realm sign-in: designer redirects to Keycloak m8flow realm,
 * then returns to Home after a successful credential submit.
 */
export async function signInAsSharedRealmUser(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await clearDesignerSession(page);
  await page.goto('/');
  await page.waitForURL(/\/realms\/m8flow\//, { timeout: 30_000 });
  await fillKeycloakCredentials(page, persona);
  await page.waitForURL((url) => url.origin.includes('localhost:6853'), {
    timeout: 60_000,
  });
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
}

/**
 * Platform admin sign-in: shared Keycloak page → Platform admin sign in
 * → master realm credentials → designer Home.
 */
export async function signInAsPlatformAdmin(
  page: Page,
  persona: DesignerPersona,
): Promise<void> {
  await clearDesignerSession(page);
  await page.goto('/');
  await page.waitForURL(/\/realms\/m8flow\//, { timeout: 30_000 });

  const platformAdmin = page.locator('#m8f-master-login-button');
  await expect(platformAdmin).toBeVisible();
  await expect(platformAdmin).not.toHaveAttribute('aria-disabled', 'true');
  await platformAdmin.click();

  await page.waitForURL(/\/realms\/master\//, { timeout: 30_000 });
  await fillKeycloakCredentials(page, persona);
  await page.waitForURL((url) => url.origin.includes('localhost:6853'), {
    timeout: 60_000,
  });
  await expect(page.getByRole('heading', { name: 'Home', exact: true })).toBeVisible();
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
