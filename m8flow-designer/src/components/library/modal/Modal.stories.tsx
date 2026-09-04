import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button"
import { Modal } from "./Modal"

const meta: Meta<typeof Modal> = {
  title: "Library/Modal",
  component: Modal,
  parameters: {
    layout: "centered",
  },
}

export default meta
type Story = StoryObj<typeof Modal>

/**
 * Reproduces the mockup's "New group" example: a title, a description
 * paragraph, a single text input, and a Cancel/Create-group footer pair.
 * The form itself lives entirely in the story — `Modal` only supplies the
 * chrome around it.
 */
export const Default: Story = {
  render: () => {
    function Wrapper() {
      const [open, setOpen] = useState(false)
      const [groupName, setGroupName] = useState("")

      return (
        <>
          <Button variant="pill" onClick={() => setOpen(true)}>
            Open modal
          </Button>
          <Modal
            open={open}
            onOpenChange={setOpen}
            title="New group"
            footer={
              <>
                <Button type="button" variant="pill-outline" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button type="button" variant="pill" onClick={() => setOpen(false)}>
                  Create group
                </Button>
              </>
            }
          >
            <p className="mb-4 text-[13.5px] text-muted-foreground">
              Groups organize related process models together.
            </p>
            <label className="block text-sm font-medium text-foreground">
              Group name
              <input
                type="text"
                value={groupName}
                onChange={(event) => setGroupName(event.target.value)}
                className="mt-1.5 block w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-ring focus:ring-3 focus:ring-ring/50"
                placeholder="e.g. Onboarding"
              />
            </label>
          </Modal>
        </>
      )
    }
    return <Wrapper />
  },
}
