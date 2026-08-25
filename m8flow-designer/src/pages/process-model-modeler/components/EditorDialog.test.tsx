import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

// Monaco needs a real browser (canvas/workers); vite.config's `test.alias`
// swaps `@monaco-editor/react` for a plain-textarea stub and `monaco-editor`
// for a light namespace stub, so this renders in jsdom.
import { EditorDialog, type EditorDialogSession } from './EditorDialog';

function makeSession(overrides: Partial<EditorDialogSession> = {}): EditorDialogSession {
  return {
    title: 'Edit Script',
    value: 'x = (1 + 2)\n',
    language: 'python',
    onSave: vi.fn(),
    ...overrides,
  };
}

describe('EditorDialog', () => {
  it('renders as a modal with the title and seeds the editor value', () => {
    render(<EditorDialog session={makeSession()} onClose={vi.fn()} />);

    expect(screen.getByRole('dialog', { name: 'Edit Script' })).toBeInTheDocument();
    expect(screen.getByLabelText('code editor')).toHaveValue('x = (1 + 2)\n');
    expect(screen.getByText('No problems')).toBeInTheDocument();
  });

  it('saves clean code and closes', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<EditorDialog session={makeSession({ onSave })} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(onSave).toHaveBeenCalledWith('x = (1 + 2)\n');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('blocks saving while a lint error remains', () => {
    const onSave = vi.fn();
    render(<EditorDialog session={makeSession({ value: 'x = (1 + 2\n' })} onClose={vi.fn()} />);

    const saveButton = screen.getByRole('button', { name: 'Save' });
    expect(saveButton).toBeDisabled();
    expect(screen.getByText('Fix 1 error before saving.')).toBeInTheDocument();

    fireEvent.click(saveButton);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('reports problem counts and lists them', () => {
    render(<EditorDialog session={makeSession({ value: 'x = 1)\n' })} onClose={vi.fn()} />);

    expect(screen.getByText('1 error, 0 warnings')).toBeInTheDocument();
    expect(screen.getByText(/Unmatched closing/)).toBeInTheDocument();
  });

  it('formats the draft when Format is clicked', () => {
    render(<EditorDialog session={makeSession({ value: 'if x:\n\tpass' })} onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Format' }));

    expect(screen.getByLabelText('code editor')).toHaveValue('if x:\n    pass\n');
  });

  it('closes without saving on Cancel', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<EditorDialog session={makeSession({ onSave })} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
