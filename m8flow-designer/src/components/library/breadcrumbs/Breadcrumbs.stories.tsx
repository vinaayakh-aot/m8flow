import type { Meta, StoryObj } from "@storybook/react-vite"

import { BackLink, Breadcrumbs } from "./Breadcrumbs"

const meta = {
  title: "Library/Breadcrumbs",
  component: Breadcrumbs,
} satisfies Meta<typeof Breadcrumbs>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    items: [
      { label: "Processes", href: "#" },
      { label: "Invoice Approvals / Finance", href: "#" },
      { label: "Two-step invoice approval" },
    ],
  },
}

export const LongFinalCrumbTruncationSafe: Story = {
  name: "Long final crumb (truncation-safe)",
  args: {
    items: [
      { label: "Processes", href: "#" },
      { label: "Invoice Approvals / Finance", href: "#" },
      {
        label:
          "Two-step-invoice-approval-with-an-unusually-long-process-model-name-that-should-wrap-instead-of-overflowing-its-container",
      },
    ],
  },
  decorators: [
    (Story) => (
      <div className="max-w-xs rounded-md border border-border p-3">
        <Story />
      </div>
    ),
  ],
}

export const BackLinkVariant: StoryObj<typeof BackLink> = {
  name: "Back link variant",
  render: (args) => <BackLink {...args} />,
  args: {
    href: "#",
    children: "Back link variant",
  },
}
