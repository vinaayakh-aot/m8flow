import * as React from "react"
import type { Meta, StoryObj } from "@storybook/react-vite"

import { Pagination } from "./Pagination"

const meta = {
  title: "Library/Pagination",
  component: Pagination,
  // Layout centering (both axes) comes from the global default in
  // .storybook/preview.ts. Pagination's root is a `justify-between` <nav>
  // meant to span whatever real container it sits in (a table footer) —
  // that's intentional, not a bug, but it means the *component* still needs
  // an explicit width or it just shrinks to its tightest content fit inside
  // Storybook's centered canvas. This decorator gives it a realistic width
  // (matching the mockup's own table width, `min-width:640px` in
  // DataTable.stories.tsx) so the range label and pager buttons show
  // genuinely spread apart, the way they do at the bottom of a normal-sized
  // table — the centered layout then centers that whole bounded box.
  //
  // Deliberately `w-[640px]` (fixed), not `max-w-[640px]`: a max-width is
  // only an upper bound, and nothing in the chain up to Storybook's
  // shrink-to-fit "centered" canvas has a definite width for it to apply
  // against, so `max-w` alone still collapsed to content size — confirmed
  // by measuring the rendered box (239px, not 640px) after the first
  // attempt, not just by eyeballing the screenshot.
  decorators: [
    (Story) => (
      <div className="w-[640px]">
        <Story />
      </div>
    ),
  ],
  // Every story below supplies its own via `ControlledPagination` wrapping
  // `page`/`onPageChange` in local state — this default only exists to
  // satisfy the type of `args` before `render` swaps it out.
  args: {
    onPageChange: () => {},
  },
} satisfies Meta<typeof Pagination>

export default meta

type Story = StoryObj<typeof meta>

/**
 * Wraps the controlled `page`/`onPageChange` props in local state so the
 * story is actually interactive, without adding any state to the component
 * itself.
 */
function ControlledPagination(props: React.ComponentProps<typeof Pagination>) {
  const [page, setPage] = React.useState(props.page)
  return <Pagination {...props} page={page} onPageChange={setPage} />
}

export const Default: Story = {
  render: (args) => <ControlledPagination {...args} />,
  args: {
    page: 1,
    totalItems: 11,
    pageSize: 5,
  },
}

export const MiddlePage: Story = {
  name: "Middle page (both buttons enabled)",
  render: (args) => <ControlledPagination {...args} />,
  args: {
    page: 2,
    totalItems: 11,
    pageSize: 5,
  },
}

export const LastPage: Story = {
  name: "Last page (next disabled, partial range)",
  render: (args) => <ControlledPagination {...args} />,
  args: {
    page: 3,
    totalItems: 11,
    pageSize: 5,
  },
}

export const SinglePage: Story = {
  name: "Single page (both prev/next disabled)",
  render: (args) => <ControlledPagination {...args} />,
  args: {
    page: 1,
    totalItems: 4,
    pageSize: 5,
  },
}
