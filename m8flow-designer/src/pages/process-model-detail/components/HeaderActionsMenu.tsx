import { Copy, Files, MoreVertical, Pencil } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { cn } from '@/lib/utils';

export type HeaderActionsMenuProps = {
  onEditIdentity?: () => void;
  onCopy?: () => void;
  onSaveAsTemplate?: () => void;
};

/** Overflow menu for secondary process-model actions. Same outside-click /
 * Escape close as the Processes list kebab — the app has no shared
 * DropdownMenu primitive. Save as template is enabled only when the caller
 * can POST templates (catalog manager, not super-admin). */
export function HeaderActionsMenu({
  onEditIdentity,
  onCopy,
  onSaveAsTemplate,
}: HeaderActionsMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(event: globalThis.MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-label="More actions"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex size-[38px] items-center justify-center rounded-full border border-border bg-card hover:bg-muted"
      >
        <MoreVertical className="size-4 text-muted-foreground" strokeWidth={2.4} />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-52 overflow-hidden rounded-xl border border-border bg-card py-1 shadow-lg"
        >
          {onEditIdentity ? (
            <HeaderMenuItem
              icon={<Pencil className="size-3.5" strokeWidth={2} />}
              label="Edit identity"
              onSelect={() => {
                setOpen(false);
                onEditIdentity();
              }}
            />
          ) : null}
          <HeaderMenuItem
            icon={<Copy className="size-3.5" strokeWidth={2} />}
            label="Copy"
            disabled={!onCopy}
            onSelect={() => {
              if (!onCopy) return;
              setOpen(false);
              onCopy();
            }}
          />
          <HeaderMenuItem
            icon={<Files className="size-3.5" strokeWidth={2} />}
            label="Save as template"
            disabled={!onSaveAsTemplate}
            onSelect={() => {
              if (!onSaveAsTemplate) return;
              setOpen(false);
              onSaveAsTemplate();
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

function HeaderMenuItem({
  icon,
  label,
  onSelect,
  disabled = false,
}: {
  icon: ReactNode;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        'flex w-full items-center gap-2.5 px-3.5 py-2 text-left text-[13px]',
        disabled
          ? 'cursor-default text-muted-foreground'
          : 'text-foreground hover:bg-muted',
      )}
    >
      <span className="text-muted-foreground">{icon}</span>
      {label}
    </button>
  );
}
