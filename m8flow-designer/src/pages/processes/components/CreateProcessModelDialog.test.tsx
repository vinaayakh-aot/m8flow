import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CreateProcessModelDialog } from './CreateProcessModelDialog';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchProcessGroups: vi.fn().mockResolvedValue([
      {
        id: 'finance',
        display_name: 'Finance',
        description: '',
        model_count: 1,
        last_run_in_seconds: null,
      },
    ]),
  };
});

describe('CreateProcessModelDialog', () => {
  it('submits group, id, and display name', async () => {
    const onCreate = vi.fn().mockResolvedValue({ id: 'finance/expense-report' });
    const onCreated = vi.fn();
    render(
      <CreateProcessModelDialog
        open
        onClose={vi.fn()}
        scopedTenantId="t1"
        onCreate={onCreate}
        onCreated={onCreated}
      />,
    );

    await waitFor(() => expect(screen.getByLabelText('Process model ID')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Process model ID'), {
      target: { value: 'expense-report' },
    });
    fireEvent.change(screen.getByLabelText('Display name'), {
      target: { value: 'Expense Report' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create process model' }));
    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith({
        group_id: 'finance',
        id: 'expense-report',
        display_name: 'Expense Report',
        description: '',
      });
    });
    expect(onCreated).toHaveBeenCalledWith('finance:expense-report');
  });
});
