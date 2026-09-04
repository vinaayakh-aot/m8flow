import * as React from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Modal } from "@/components/library/modal/Modal"

export interface WizardModalStep {
  title: React.ReactNode
  body: React.ReactNode
}

export interface WizardModalProps {
  open: boolean
  /** The wizard's steps, in order. Both the header title and the body swap
   * per-step (the mockup's "Connect a source" / "Map the fields" /
   * "Review & launch" example). */
  steps: WizardModalStep[]
  /** Called when the dialog should close before the wizard finished — the
   * built-in round close (X) button, Escape, or an overlay click. */
  onClose: () => void
  /** Called when "Finish" (Continue on the final step) is activated. The
   * wizard doesn't close itself first — callers decide whether finishing
   * also closes the dialog. */
  onComplete: () => void
}

/**
 * Built on top of `Modal`, adding the mockup's "Multi-page modal" chrome:
 * step dots, a "Step N of M" label, per-step title/body content, and
 * Back/Continue-or-Finish footer buttons (Back disabled on step 1, the
 * final step's button reads "Finish").
 *
 * Manages its own current-step state internally — callers only pass `steps`
 * plus `onClose`/`onComplete`, matching the mockup's own state model
 * (`step`, `stepOpen`). The step resets back to the first one every time the
 * wizard transitions from closed to open, so reopening it always starts
 * fresh.
 */
function WizardModal({ open, steps, onClose, onComplete }: WizardModalProps) {
  const [step, setStep] = React.useState(0)

  React.useEffect(() => {
    if (open) {
      setStep(0)
    }
  }, [open])

  const stepCount = steps.length
  const activeStep = Math.min(step, Math.max(stepCount - 1, 0))
  const current = steps[activeStep]
  const isFirstStep = activeStep === 0
  const isLastStep = activeStep >= stepCount - 1

  function handleBack() {
    setStep((prev) => Math.max(0, prev - 1))
  }

  function handleContinue() {
    if (isLastStep) {
      onComplete()
      return
    }
    setStep((prev) => Math.min(stepCount - 1, prev + 1))
  }

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          onClose()
        }
      }}
      title={current?.title}
      footer={
        <div className="flex w-full items-center justify-between gap-2.5">
          <Button type="button" variant="pill-outline" onClick={handleBack} disabled={isFirstStep}>
            Back
          </Button>
          <Button type="button" variant="pill" onClick={handleContinue}>
            {isLastStep ? "Finish" : "Continue"}
          </Button>
        </div>
      }
    >
      <div data-slot="wizard-modal-steps" className="mb-[18px] flex items-center gap-1.5">
        {steps.map((_, index) => (
          <span
            key={index}
            aria-hidden="true"
            className={cn("h-1 w-5 rounded-full", index <= activeStep ? "bg-nav-active" : "bg-muted")}
          />
        ))}
        <span className="ml-1.5 text-xs text-muted-foreground">
          Step {activeStep + 1} of {stepCount}
        </span>
      </div>
      <div className="mb-5 min-h-24 text-[13.5px] leading-normal text-muted-foreground">
        {current?.body}
      </div>
    </Modal>
  )
}

export { WizardModal }
