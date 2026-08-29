import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { Sidebar } from './Sidebar';

describe('Sidebar live nav', () => {
  it('renders Home and Processes as links inside a router', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Sidebar />,
        },
      ],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Processes' })).toHaveAttribute(
      'href',
      '/processes',
    );
    // Process Instances + task-state map, ticket 02: now a real link too.
    expect(screen.getByRole('link', { name: 'Process Instances' })).toHaveAttribute(
      'href',
      '/process-instances',
    );
    // Templates modeler map, ticket 02: Setup's "Templates" child is a real
    // link now, unlike its still-inert siblings (Configuration/Connectors).
    expect(screen.getByRole('link', { name: 'Templates' })).toHaveAttribute(
      'href',
      '/templates',
    );
    expect(screen.getByText('Configuration')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Configuration' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Authentications' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Tenants' })).not.toBeInTheDocument();
    expect(screen.getByText('Tenants')).toBeInTheDocument();
    expect(screen.queryByText('Tenant Management')).not.toBeInTheDocument();
  });

  it('shows a read-only active tenant badge and no tenant combobox', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Sidebar activeTenantLabel="Acme Corp" />,
        },
      ],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.getByTestId('nav-tenant-name')).toHaveTextContent('Acme Corp');
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('prefers the super-admin tenant selector over the active-tenant badge', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: (
            <Sidebar
              showTenantSelector
              tenants={[{ id: 't1', name: 'Tenant One' }]}
              activeTenantLabel="Acme Corp"
            />
          ),
        },
      ],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.getByRole('combobox', { name: /Tenant/ })).toBeInTheDocument();
    expect(screen.queryByTestId('nav-tenant-name')).not.toBeInTheDocument();
  });

  it('shows Setup → Authentications when the role can read them', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Sidebar showAuthentications />,
        },
        {
          path: '/authentications',
          element: <Sidebar showAuthentications />,
        },
      ],
      { initialEntries: ['/'] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.getByRole('link', { name: 'Authentications' })).toHaveAttribute(
      'href',
      '/authentications',
    );
  });

  it('makes Tenants a live /tenants link for super-admin', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Sidebar showTenantsNav />,
        },
        {
          path: '/tenants',
          element: <Sidebar showTenantsNav />,
        },
      ],
      { initialEntries: ['/tenants'] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.getByRole('link', { name: 'Tenants' })).toHaveAttribute('href', '/tenants');
    expect(screen.getByRole('link', { name: 'Tenants' })).toHaveAttribute('aria-current', 'page');
  });

  it('shows Tenant Management as a live link when the role can manage the tenant', () => {
    const router = createMemoryRouter(
      [
        {
          path: '/',
          element: <Sidebar showTenantManagement />,
        },
        {
          path: '/tenant-management',
          element: <Sidebar showTenantManagement />,
        },
      ],
      { initialEntries: ['/tenant-management'] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.getByRole('link', { name: 'Tenant Management' })).toHaveAttribute(
      'href',
      '/tenant-management',
    );
    expect(screen.getByRole('link', { name: 'Tenant Management' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('stays inert (no links) outside a router for prototypes', () => {
    render(<Sidebar activeNavId="home" />);

    expect(screen.queryByRole('link', { name: 'Home' })).not.toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Processes')).toBeInTheDocument();
  });
});
