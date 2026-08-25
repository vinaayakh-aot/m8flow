import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';

const mockIsLoggedIn = vi.fn();
const mockResumeLoginAfterLogout = vi.fn();
const mockEnsureSelectedTenantCookie = vi.fn();

vi.mock('@/lib/auth', () => ({
  isLoggedIn: () => mockIsLoggedIn(),
  resumeLoginAfterLogout: () => mockResumeLoginAfterLogout(),
  ensureSelectedTenantCookie: () => mockEnsureSelectedTenantCookie(),
  getCurrentUser: () => ({ username: 'editor', email: null }),
  isSuperAdmin: () => false,
  logout: () => undefined,
}));

vi.mock('@/components/layout/AppShell', async () => {
  const { Outlet } = await import('react-router-dom');
  return {
    AppShell: () => (
      <div>
        <div>app-shell</div>
        <Outlet />
      </div>
    ),
  };
});

vi.mock('@/pages/home/HomePage', () => ({
  default: () => <div>home-page</div>,
}));

vi.mock('@/pages/processes/ProcessesPage', () => ({
  default: () => <div>processes-page</div>,
}));

vi.mock('@/pages/process-model-detail/ProcessModelDetailPage', () => ({
  default: () => <div>process-model-detail-page</div>,
}));

describe('App', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('shows the redirecting copy and resumes Keycloak login when logged out', () => {
    mockIsLoggedIn.mockReturnValue(false);

    render(<App />);

    expect(screen.getByText('Redirecting to sign in...')).toBeInTheDocument();
    expect(screen.queryByText('home-page')).not.toBeInTheDocument();
    expect(mockResumeLoginAfterLogout).toHaveBeenCalledTimes(1);
  });

  it('renders the app shell and Home route when the user is logged in', () => {
    mockIsLoggedIn.mockReturnValue(true);

    render(<App />);

    expect(screen.getByText('app-shell')).toBeInTheDocument();
    expect(screen.getByText('home-page')).toBeInTheDocument();
    expect(screen.queryByText('Redirecting to sign in...')).not.toBeInTheDocument();
    expect(mockResumeLoginAfterLogout).not.toHaveBeenCalled();
    expect(mockEnsureSelectedTenantCookie).toHaveBeenCalled();
  });
});
