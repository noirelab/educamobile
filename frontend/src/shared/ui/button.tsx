import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/shared/lib/utils"

const buttonVariants = cva(
  "focus-ring inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[14px] font-sans text-button transition-[transform,box-shadow,background-color,opacity] duration-[250ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-px active:scale-[.97] disabled:pointer-events-none disabled:opacity-50 disabled:hover:translate-y-0 [&_svg]:pointer-events-none [&_svg]:size-[18px] [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[0_8px_20px_rgba(15,118,110,0.25)] hover:bg-accent-hover",
        secondary:
          "border border-line bg-glass-strong text-ink shadow-sm hover:bg-white/80",
        outline:
          "border border-line bg-glass-strong text-ink shadow-sm hover:bg-white/80",
        ghost:
          "bg-transparent text-ink-muted hover:bg-[rgba(15,30,51,0.06)] hover:text-ink",
        destructive:
          "bg-danger text-white shadow-sm hover:brightness-95",
        "danger-outline":
          "border border-danger bg-transparent text-danger hover:bg-[rgba(220,38,38,0.08)]",
        link: "text-accent underline-offset-4 hover:underline hover:translate-y-0 active:scale-100",
      },
      size: {
        default: "h-11 px-[18px]",
        sm: "h-9 rounded-[12px] px-3.5 text-label",
        lg: "h-11 px-[18px]",
        icon: "h-10 w-10 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
