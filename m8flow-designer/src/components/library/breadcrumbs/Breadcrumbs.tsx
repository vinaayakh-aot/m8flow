import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"

export interface BreadcrumbItem {
  label: string
  /**
   * Rendered as a plain `<a>` when present. Deliberately not
   * `react-router-dom`'s `Link` — this component must render without
   * assuming router context (per the map's "self-contained" decision). A
   * page composing this with client-side routing can intercept clicks on
   * the rendered anchors itself if it needs to.
   */
  href?: string
}

export interface BreadcrumbsProps
  extends Omit<React.ComponentProps<"nav">, "children"> {
  /** Ordered crumb trail. The last item is always rendered as bold static text, never a link, regardless of whether it has an `href`. */
  items: BreadcrumbItem[]
}

/**
 * Breadcrumb trail: every item but the last renders as a link (or plain text
 * if it has no `href`) followed by a chevron separator; the last item
 * renders as bold, non-interactive text and is allowed to wrap
 * (`overflow-wrap: anywhere`) so a long final crumb (e.g. a process model
 * name) doesn't overflow its container.
 */
const Breadcrumbs = React.forwardRef<HTMLElement, BreadcrumbsProps>(
  ({ items, className, ...props }, ref) => {
    return (
      <nav
        ref={ref}
        data-slot="breadcrumbs"
        aria-label="Breadcrumb"
        className={cn("text-[13.5px]", className)}
        {...props}
      >
        <ol className="flex flex-wrap items-center gap-1.5">
          {items.map((item, index) => {
            const isLast = index === items.length - 1

            return (
              <li key={`${item.label}-${index}`} className="flex items-center gap-1.5">
                {isLast ? (
                  <span
                    aria-current="page"
                    className="font-semibold text-foreground [overflow-wrap:anywhere]"
                  >
                    {item.label}
                  </span>
                ) : (
                  <>
                    {item.href ? (
                      <a
                        href={item.href}
                        className="font-medium text-primary no-underline hover:underline"
                      >
                        {item.label}
                      </a>
                    ) : (
                      <span className="font-medium text-muted-foreground">{item.label}</span>
                    )}
                    <ChevronRight
                      className="size-[13px] shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </>
                )}
              </li>
            )
          })}
        </ol>
      </nav>
    )
  }
)
Breadcrumbs.displayName = "Breadcrumbs"

export interface BackLinkProps extends React.ComponentProps<"a"> {
  children: React.ReactNode
}

/**
 * "← Back link variant" from the mockup's Breadcrumbs section — kept in the
 * same folder/family as `Breadcrumbs` since the mockup presents them
 * together, but exported independently so an app that only ever needs one
 * of the two still tree-shakes out the other.
 */
const BackLink = React.forwardRef<HTMLAnchorElement, BackLinkProps>(
  ({ className, children, ...props }, ref) => (
    <a
      ref={ref}
      data-slot="back-link"
      className={cn(
        "inline-flex items-center gap-1.5 text-[13px] font-semibold text-foreground no-underline hover:underline",
        className
      )}
      {...props}
    >
      <ChevronLeft className="size-3.5 shrink-0" aria-hidden="true" />
      {children}
    </a>
  )
)
BackLink.displayName = "BackLink"

export { Breadcrumbs, BackLink }
