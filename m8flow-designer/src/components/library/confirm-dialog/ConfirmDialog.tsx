import * as React from "react"
import { AlertTriangle } from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { cn } from "@/lib/utils"

export type ConfirmDialogTone = "destructive" | "default"

export interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  description?: React.ReactNode
  cancelLabel?: string
  confirmLabel?: string
  /** Called when the confirm action is activated. The dialog itself closes
   * (via `onOpenChange(false)`) right after — callers don't need to close it
   * themselves inside this callback. */
  onConfirm: () => void
  /**
   * `"destructive"` (default) matches the mockup's "Delete this process
   * model?" example: a solid red pill confirm button next to the pale
   * outline Cancel pill. `"default"` is for confirmations that aren't
   * destructive (e.g. "Publish this process?") and shouldn't read as a
   * warning.
   */
  tone?: ConfirmDialogTone
}

/**
 * `library/` wrapper around `ui/alert-dialog.tsx`'s primitives, reproducing
 * the mockup's confirmation-dialog pattern: a circular warning-icon badge,
 * title + description, and a Cancel/Confirm footer.
 *
 * Button treatment for the confirm action: the mockup's swatch is a solid
 * `background:var(--status-error)` pill (`border-radius:999px`), not
 * `ui/button.tsx`'s existing `destructive` variant (a pale
 * `bg-destructive/10` outline treatment, and `rounded-lg` rather than a
 * pill — it would visually clash sitting next to the pill-shaped Cancel
 * button). So this layers solid destructive colors on top of
 * `AlertDialogAction`'s existing `pill` shape via `className`, rather than
 * switching variants — same one-off-override pattern `AlertDialogAction`/
 * `AlertDialogCancel` already use to stay generic (see ui/alert-dialog.tsx).
 * `tone="default"` leaves `AlertDialogAction` at its own default styling
 * (`pill` / `bg-nav-active`) and skips the red icon badge for a neutral one.
 */
function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  cancelLabel = "Cancel",
  confirmLabel = "Confirm",
  onConfirm,
  tone = "destructive",
}: ConfirmDialogProps) {
  const isDestructive = tone === "destructive"

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-slot="confirm-dialog-content">
        <AlertDialogHeader>
          <span
            data-slot="confirm-dialog-icon"
            className={cn(
              "flex size-[38px] flex-none items-center justify-center rounded-full",
              isDestructive ? "bg-destructive/10" : "bg-primary/10"
            )}
          >
            <AlertTriangle
              className={cn("size-[18px]", isDestructive ? "text-destructive" : "text-primary")}
              aria-hidden="true"
            />
          </span>
          <div>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            {description ? (
              <AlertDialogDescription className="mt-1.5">{description}</AlertDialogDescription>
            ) : null}
          </div>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={cn(
              isDestructive && "bg-destructive text-white hover:bg-destructive/90"
            )}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export { ConfirmDialog }
