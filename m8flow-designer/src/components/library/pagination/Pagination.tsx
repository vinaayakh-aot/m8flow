import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"

export interface PaginationProps
  extends Omit<React.ComponentProps<"nav">, "onChange"> {
  /**
   * Current page, 1-indexed. Not required to already be in `[1, totalPages]`
   * — e.g. a caller may still be showing `page={4}` for a moment after
   * `totalItems` shrinks under it. Clamped internally for display/disabled
   * state so that transient case never renders a blank/out-of-range page.
   */
  page: number
  /**
   * Called with the next 1-indexed page number when the prev/next button or
   * a page number button is activated. Never called for the already-current
   * page, or past the first/last page (those buttons are `disabled`).
   */
  onPageChange: (page: number) => void
  totalItems: number
  pageSize: number
}

/**
 * Prev/next round icon buttons + numbered page buttons + an "x–y of z" range
 * label, per the mockup's table pager. Page count is derived from
 * `totalItems`/`pageSize` internally — callers never compute it themselves.
 *
 * Kept in its own module, independent of `DataTable`, so a consumer that
 * paginates something other than a `DataTable` (or vice versa) only pulls in
 * the piece it needs.
 */
const Pagination = React.forwardRef<HTMLElement, PaginationProps>(
  ({ page, onPageChange, totalItems, pageSize, className, ...props }, ref) => {
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
    const currentPage = Math.min(Math.max(page, 1), totalPages)

    const rangeStart = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1
    const rangeEnd = Math.min(currentPage * pageSize, totalItems)

    const goTo = (target: number) => {
      if (target === currentPage || target < 1 || target > totalPages) return
      onPageChange(target)
    }

    return (
      <nav
        ref={ref}
        data-slot="pagination"
        aria-label="Pagination"
        className={cn("flex items-center justify-between gap-4", className)}
        {...props}
      >
        <span data-slot="pagination-range" className="text-[13px] text-muted-foreground">
          {rangeStart}–{rangeEnd} of {totalItems}
        </span>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            data-slot="pagination-prev"
            aria-label="Previous page"
            disabled={currentPage === 1}
            onClick={() => goTo(currentPage - 1)}
            className="flex size-[30px] shrink-0 items-center justify-center rounded-full border border-border text-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
          </button>

          {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => {
            const isCurrent = pageNumber === currentPage

            return (
              <button
                key={pageNumber}
                type="button"
                data-slot="pagination-page"
                aria-label={`Page ${pageNumber}`}
                aria-current={isCurrent ? "page" : undefined}
                onClick={() => goTo(pageNumber)}
                className={cn(
                  "flex h-[30px] min-w-[30px] shrink-0 items-center justify-center rounded-full px-1.5 font-mono text-[12.5px]",
                  // Mockup: current page gets a solid foreground/white treatment,
                  // matching `ui/button.tsx`'s `pill-dark` variant's own
                  // `bg-foreground` + `text-white` pairing rather than inventing
                  // a new token for "white text on dark fill".
                  isCurrent
                    ? "bg-foreground text-white"
                    : "text-muted-foreground hover:bg-muted"
                )}
              >
                {pageNumber}
              </button>
            )
          })}

          <button
            type="button"
            data-slot="pagination-next"
            aria-label="Next page"
            disabled={currentPage === totalPages}
            onClick={() => goTo(currentPage + 1)}
            className="flex size-[30px] shrink-0 items-center justify-center rounded-full border border-border text-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            <ChevronRight className="size-4" aria-hidden="true" />
          </button>
        </div>
      </nav>
    )
  }
)
Pagination.displayName = "Pagination"

export { Pagination }
