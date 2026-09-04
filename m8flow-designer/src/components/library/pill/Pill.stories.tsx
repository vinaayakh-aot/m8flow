import type { Meta, StoryObj } from "@storybook/react-vite"

import { Pill } from "./Pill"

const meta: Meta<typeof Pill> = {
  title: "Library/Pill",
  component: Pill,
  parameters: {
    layout: "centered",
  },
  args: {
    tone: "success",
    dot: true,
    children: "Published",
  },
  argTypes: {
    tone: {
      control: "select",
      options: ["success", "error", "warning", "muted"],
    },
  },
}

export default meta

type Story = StoryObj<typeof Pill>

// The mockup's four status-dot pill examples, one per tone.
export const Success: Story = {
  args: { tone: "success", children: "Published" },
}

export const Error: Story = {
  args: { tone: "error", children: "Needs attention" },
}

export const Warning: Story = {
  args: { tone: "warning", children: "Paused" },
}

export const Muted: Story = {
  args: { tone: "muted", children: "Draft" },
}

export const AllStatusTones: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2.5">
      <Pill tone="success">Published</Pill>
      <Pill tone="error">Needs attention</Pill>
      <Pill tone="warning">Paused</Pill>
      <Pill tone="muted">Draft</Pill>
    </div>
  ),
}

// The mockup's plain static tag pill pattern: same visual family, no dot,
// no status meaning.
export const PlainTag: Story = {
  name: "Plain tag (dot={false})",
  args: { dot: false, tone: "muted", children: "Ticketmaster API" },
}

export const PlainTags: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Pill dot={false}>Ticketmaster API</Pill>
      <Pill dot={false}>Spotify OAuth</Pill>
    </div>
  ),
}
