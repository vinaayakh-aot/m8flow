import { Badge } from '@/components/ui/badge';

/**
 * Process-instance status vocabulary as shown in the mockup's "Recent
 * process instances" table. Unknown backend statuses fall back to a muted
 * secondary pill so the table still renders.
 */
export type ProcessInstanceStatus = 'complete' | 'error' | 'user_input_required';

const STATUS_CONFIG: Record<
  string,
  { label: string; variant: 'success' | 'destructive' | 'warning' | 'secondary'; dot: boolean }
> = {
  complete: { label: 'Complete', variant: 'success', dot: true },
  error: { label: 'Error', variant: 'destructive', dot: true },
  user_input_required: { label: 'User Input Required', variant: 'warning', dot: false },
};

function humanize(status: string): string {
  return status
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? {
    label: humanize(status),
    variant: 'secondary' as const,
    dot: false,
  };
  return (
    <Badge variant={config.variant} className="gap-1.5">
      {config.dot ? <span className="size-1.5 rounded-full bg-current" /> : null}
      {config.label}
    </Badge>
  );
}
