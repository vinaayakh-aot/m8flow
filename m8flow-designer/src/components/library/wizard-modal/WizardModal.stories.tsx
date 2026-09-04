import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { Button } from "@/components/ui/button"
import { WizardModal, type WizardModalStep } from "./WizardModal"

const meta: Meta<typeof WizardModal> = {
  title: "Library/WizardModal",
  component: WizardModal,
  parameters: {
    layout: "centered",
  },
}

export default meta
type Story = StoryObj<typeof WizardModal>

/** The mockup's three-step "setup wizard" example. */
const steps: WizardModalStep[] = [
  {
    title: "Connect a source",
    body: "Choose where this process pulls its trigger data from — a form, an API, or a scheduled timer.",
  },
  {
    title: "Map the fields",
    body: "Match incoming fields to the variables this process model expects.",
  },
  {
    title: "Review & launch",
    body: "Confirm the connection and mapping, then turn the process on.",
  },
]

export const Default: Story = {
  render: () => {
    function Wrapper() {
      const [open, setOpen] = useState(false)

      return (
        <>
          <Button variant="pill" onClick={() => setOpen(true)}>
            Open setup wizard
          </Button>
          <WizardModal
            open={open}
            steps={steps}
            onClose={() => setOpen(false)}
            onComplete={() => setOpen(false)}
          />
        </>
      )
    }
    return <Wrapper />
  },
}
