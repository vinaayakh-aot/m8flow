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

  it('stays inert (no links) outside a router for prototypes', () => {
    render(<Sidebar activeNavId="home" />);

    expect(screen.queryByRole('link', { name: 'Home' })).not.toBeInTheDocument();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Processes')).toBeInTheDocument();
  });
});
