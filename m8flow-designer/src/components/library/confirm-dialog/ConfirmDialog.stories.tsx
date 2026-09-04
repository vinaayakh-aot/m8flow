import * as React from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button"
import { ConfirmDialog, type ConfirmDialogProps } from "./ConfirmDialog"

const meta: Meta<typeof ConfirmDialog> = {
  title: "Library/ConfirmDialog",
  component: ConfirmDialog,
}
export default meta

type Story = StoryObj<typeof ConfirmDialog>

/**
 * Wraps the (controlled) `ConfirmDialog` with its own open/close state so
 * each story is interactive in the Storybook canvas, rather than rendering
 * permanently-open (which `ConfirmDialogProps["open"]` alone can't express
 * as a static arg without a trigger to reopen it after Cancel/Confirm).
 */
function ConfirmDialogDemo({
  triggerLabel,
  ...props
}: Omit<ConfirmDialogProps, "open" | "onOpenChange"> & { triggerLabel: string }) {
  const [open, setOpen] = React.useState(false)
  return (
    <>
      <Button variant="pill" onClick={() => setOpen(true)}>
        {triggerLabel}
      </Button>
      <ConfirmDialog {...props} open={open} onOpenChange={setOpen} />
    </>
  )
}

// Reproduces the mockup's "Delete this process model?" confirmation example
// (Components.dc.html's "Confirmation dialog" section): destructive tone,
// solid red pill confirm button next to the pale outline Cancel pill.
export const DeleteProcessModel: Story = {
  render: () => (
    <ConfirmDialogDemo
      triggerLabel="Delete process model"
      title="Delete this process model?"
      description="This removes the model, its files and run history. This can't be undone."
      cancelLabel="Cancel"
      confirmLabel="Delete"
      tone="destructive"
      onConfirm={() => {
        console.log("confirmed")
      }}
    />
  ),
}

// A non-destructive confirmation, showing `tone="default"` swaps the
// solid-red confirm button and warning-red icon badge for a neutral look.
export const PublishProcess: Story = {
  render: () => (
    <ConfirmDialogDemo
      triggerLabel="Publish process"
      title="Publish this process?"
      description="This makes the current draft the live version for new instances."
      cancelLabel="Cancel"
      confirmLabel="Publish"
      tone="default"
      onConfirm={() => {
        console.log("confirmed")
      }}
    />
  ),
}
