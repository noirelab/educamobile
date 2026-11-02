import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/utils'

type PageHeaderProps = {
  title: string
  description?: string
  actions?: ReactNode
  actionsAtLg?: boolean
  children?: ReactNode
}

export function PageHeader({ title, description, actions, actionsAtLg = false, children }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4">
      <div
        className={cn(
          'flex flex-col gap-4',
          actionsAtLg ? 'lg:flex-row lg:items-end lg:justify-between' : 'md:flex-row md:items-end md:justify-between',
        )}
      >
        <div className="min-w-0">
          <h1 className="text-title font-semibold text-ink">{title}</h1>
          {description && <p className="mt-1 text-body text-ink-muted">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-3">{children}</div>}
    </div>
  )
}
