import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProcessesModelsList } from './ProcessesModelsList';
import { ApiError, type ProcessModelListItem } from '@/lib/api';

const MODELS: ProcessModelListItem[] = [
  {
    id: 'finance/invoice-approval',
    display_name: 'Invoice Approval',
    group_id: 'finance',
    group_display_name: 'Finance',
    last_run_in_seconds: 1_700_000_000,
    runs_30d: 4,
  },
  {
    id: 'onboarding/new-hire',
    display_name: 'New Hire',
    group_id: 'onboarding',
    group_display_name: 'Onboarding',
    last_run_in_seconds: null,
    runs_30d: 0,
  },
];

describe('ProcessesModelsList', () => {
  it('renders models and opens on Open click', () => {
    const onOpen = vi.fn();
    render(
      <ProcessesModelsList
        models={MODELS}
        onOpenModel={onOpen}
      />,
    );

    expect(screen.getByText('Invoice Approval')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'Open' })[0]);
    expect(onOpen).toHaveBeenCalledWith(MODELS[0]);
  });

  it('filters by search', () => {
    render(<ProcessesModelsList models={MODELS} />);
    fireEvent.change(screen.getByLabelText('Search process models'), {
      target: { value: 'hire' },
    });
    expect(screen.getByText('New Hire')).toBeInTheDocument();
    expect(screen.queryByText('Invoice Approval')).not.toBeInTheDocument();
  });

  it('shows group empty state and Clear filter', () => {
    const onClear = vi.fn();
    render(
      <ProcessesModelsList
        models={[]}
        groupFilter="finance"
        scopeLabel="Finance"
        totalUnfilteredCount={12}
        onClearGroupFilter={onClear}
      />,
    );
    expect(screen.getByText('No models in this group')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filter' }));
    expect(onClear).toHaveBeenCalled();
  });

  it('no longer renders a "Browse groups" button (scope pill replaces it)', () => {
    render(<ProcessesModelsList models={MODELS} />);
    expect(screen.queryByRole('button', { name: 'Browse groups' })).not.toBeInTheDocument();
  });

  it('starts a model from the Start button', () => {
    const onStart = vi.fn();
    render(<ProcessesModelsList models={MODELS} onStartModel={onStart} />);
    fireEvent.click(screen.getAllByRole('button', { name: 'Start' })[0]);
    expect(onStart).toHaveBeenCalledWith(MODELS[0]);
  });

  it('opens the overflow menu and confirms delete', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<ProcessesModelsList models={MODELS} onDeleteModel={onDelete} />);

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[0]);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Delete process model?')).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(onDelete).toHaveBeenCalledWith(MODELS[0]));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('surfaces the has-instances (409) reason in the delete dialog', async () => {
    const onDelete = vi.fn().mockRejectedValue(new ApiError('/x', 409, 'DELETE'));
    render(<ProcessesModelsList models={MODELS} onDeleteModel={onDelete} />);

    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[0]);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    expect(await within(dialog).findByText(/still has process instances/i)).toBeInTheDocument();
    // Dialog stays open so the user can read the reason.
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('does not offer Delete when onDeleteModel is not provided', () => {
    render(<ProcessesModelsList models={MODELS} />);
    fireEvent.click(screen.getAllByRole('button', { name: 'More actions' })[0]);
    expect(screen.queryByRole('menuitem', { name: 'Delete' })).not.toBeInTheDocument();
  });
});
