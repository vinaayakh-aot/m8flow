export type SaveStatus = 'saving' | 'saved' | 'error';

const STYLES: Record<SaveStatus, string> = {
  saving: 'bg-muted text-muted-foreground',
  saved: 'bg-success/15 text-success',
  error: 'bg-destructive/15 text-destructive',
};

const LABELS: Record<SaveStatus, string> = {
  saving: 'Saving…',
  saved: 'Saved',
  error: 'Save failed',
};

/**
 * The pill and the Save button (SaveButton.tsx) are never shown together —
 * decided on the manual-save ticket: dirty state shows the Save button;
 * clean/saving/error states show this pill. "error" is a brief flash
 * (timed by the page) before reverting to the Save button, not a
 * persistent state.
 */
export function SavedStatusPill({ status }: { status: SaveStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
