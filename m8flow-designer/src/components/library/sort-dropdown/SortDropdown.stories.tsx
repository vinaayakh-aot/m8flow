import * as React from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { SortDropdown } from "./SortDropdown"

const options = [
  { label: "Last run", value: "last-run" },
  { label: "Name", value: "name" },
  { label: "Status", value: "status" },
]

const meta = {
  title: "Library/SortDropdown",
  component: SortDropdown,
  args: {
    options,
    value: options[0].value,
    onChange: () => {},
  },
} satisfies Meta<typeof SortDropdown>

export default meta

type Story = StoryObj<typeof meta>

/**
 * Wraps the controlled `value`/`onChange` props in local state so the story
 * is actually interactive, without adding any state/coupling to the
 * component itself — same pattern as `library/search-bar`'s stories.
 */
function ControlledSortDropdown(props: React.ComponentProps<typeof SortDropdown>) {
  const [value, setValue] = React.useState(props.value)
  return <SortDropdown {...props} value={value} onChange={setValue} />
}

export const Default: Story = {
  render: (args) => <ControlledSortDropdown {...args} />,
}

export const NameSelected: Story = {
  render: (args) => <ControlledSortDropdown {...args} />,
  args: {
    value: "name",
  },
}
