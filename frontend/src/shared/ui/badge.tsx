import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/shared/lib/utils"

const badgeVariants = cva(
  "focus-ring inline-flex h-6 items-center whitespace-nowrap rounded-full px-2.5 text-caption font-semibold",
  {
    variants: {
      variant: {
        default: "bg-accent-soft text-accent",
        success: "bg-[rgba(22,163,74,0.15)] text-success-text",
        warning: "bg-[rgba(245,158,11,0.15)] text-warning-text",
        muted: "bg-[rgba(15,30,51,0.08)] text-ink-muted",
        destructive: "bg-[rgba(220,38,38,0.1)] text-danger",
        secondary: "bg-glass-strong text-ink",
        outline: "border border-line text-ink",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge }
