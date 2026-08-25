import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MyTasksList } from './MyTasksList';

describe('MyTasksList', () => {
  it('renders title, waiting-on line, and verbose relative time', () => {
    const nowSec = Math.floor(Date.now() / 1000);
    render(
      <MyTasksList
        tasks={[
          {
            id: 1,
            task_title: 'Submit WFH Request',
            task_name: 'Submit_WFH',
            tenant_id: 'aot-demo',
            tenant_name: 'aot-demo',
            lane_name: 'aot-demo:reviewer',
            created_at_in_seconds: nowSec - 10 * 3600,
            process_instance_id: 100,
          },
        ]}
      />,
    );

    expect(screen.getByText('My tasks')).toBeInTheDocument();
    expect(screen.getByText('View all')).toBeInTheDocument();
    expect(screen.getByText('Submit WFH Request')).toBeInTheDocument();
    expect(screen.getByText('aot-demo · waiting on aot-demo:reviewer')).toBeInTheDocument();
    expect(screen.getByText('about 10 hours ago')).toBeInTheDocument();
  });

  it('falls back to task_name when task_title is empty', () => {
    render(
      <MyTasksList
        tasks={[
          {
            id: 2,
            task_title: null,
            task_name: 'Approve',
            tenant_id: 't1',
            tenant_name: 't1',
            lane_name: null,
            created_at_in_seconds: null,
            process_instance_id: 1,
          },
        ]}
      />,
    );
    expect(screen.getByText('Approve')).toBeInTheDocument();
    expect(screen.getByText('t1 · waiting on —')).toBeInTheDocument();
  });

  it('shows empty copy when there are no tasks', () => {
    render(<MyTasksList tasks={[]} />);
    expect(screen.getByText('No pending tasks.')).toBeInTheDocument();
  });
});
