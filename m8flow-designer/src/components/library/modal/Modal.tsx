import * as React from "react"

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export interface ModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  /** Arbitrary body content. Deliberately not typed/structured any further
   * here — e.g. the mockup's "New group" text-input form belongs in this
   * component's own Storybook story, not baked into `Modal` itself, so any
   * other caller (including `WizardModal`) can put whatever it needs here. */
  children?: React.ReactNode
  /** Right-aligned footer action row (the mockup's Cancel/Create-group pair).
   * Omit entirely for a modal with no footer actions. */
  footer?: React.ReactNode
}

/**
 * General-purpose chrome around `ui/dialog.tsx`, matching the mockup's
 * "Modal" section: a title + round close (X) button in the header, arbitrary
 * body content via `children`, and a footer slot for actions. The close
 * button is `DialogContent`'s own built-in `showCloseButton`, left at its
 * default `true` — no second close button is built here.
 *
 * This is the general-purpose wrapper other things (including `WizardModal`)
 * build on top of. It intentionally does not know about any specific body
 * content or form.
 *
 * Two mockup-matched tweaks layered on top of `DialogContent`'s shadcn
 * defaults via `className`/`overlayClassName` (both are the exact per-instance
 * escape hatches `DialogContent` already exposes for this — see its own
 * comments in `ui/dialog.tsx`):
 * - The overlay tint (`rgba(44,55,60,.40)`) is darker than the shadcn default
 *   (`bg-black/10`), so it's overridden to `bg-foreground/40` (this app's
 *   `--foreground` is a dark gunmetal gray, matching the mockup's tint).
 * - `DialogContent` ships with no `shadow-*` utility at all; the mockup calls
 *   for `box-shadow: var(--shadow-lg)`, mapped onto Tailwind's own `shadow-lg`
 *   utility (the same one `ui/alert-dialog.tsx` already uses for its panel).
 */
function Modal({ open, onOpenChange, title, children, footer }: ModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-slot="modal-content"
        overlayClassName="bg-foreground/40"
        className="max-w-[460px] gap-3 p-6 shadow-lg sm:max-w-[460px]"
      >
        <DialogHeader>
          <DialogTitle className="pr-6 font-display text-[19px] leading-tight font-semibold text-foreground">
            {title}
          </DialogTitle>
        </DialogHeader>
        {children}
        {footer ? (
          <DialogFooter
            data-slot="modal-footer"
            className="mx-0 mb-0 flex-row items-center justify-end gap-2.5 rounded-none border-t-0 bg-transparent p-0"
          >
            {footer}
          </DialogFooter>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

export { Modal }
