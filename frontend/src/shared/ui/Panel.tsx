import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/utils'
import { useLiquidGlass } from './useLiquidGlass'

type PanelProps = {
  title?: string
  caption?: string
  actions?: ReactNode
  dense?: boolean
  liquid?: boolean
  className?: string
  children?: ReactNode
}

export function Panel({ title, caption, actions, dense = false, liquid = true, className, children }: PanelProps) {
  const ref = useLiquidGlass<HTMLElement>(liquid && !dense, 22)
  return (
    <section ref={ref} className={cn('glass p-5 lg:p-6', liquid && !dense && 'liquid', dense && 'glass-dense', className)}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
          {title && (
            <div className="min-w-0">
              <h2 className="text-section font-semibold text-ink">{title}</h2>
              {caption && <p className="mt-0.5 text-caption text-ink-muted">{caption}</p>}
            </div>
          )}
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
