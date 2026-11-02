import type { ElementType, HTMLAttributes } from 'react'
import { cn } from '@/shared/lib/utils'
import { useLiquidGlass } from './useLiquidGlass'

type GlassPanelProps = HTMLAttributes<HTMLElement> & {
  as?: ElementType
  liquid?: boolean
  strong?: boolean
  dense?: boolean
  interactive?: boolean
}

export function GlassPanel({ as: Tag = 'div', liquid = true, strong = false, dense = false, interactive = false, className, ...props }: GlassPanelProps) {
  const ref = useLiquidGlass<HTMLElement>(liquid && !dense, 22, interactive)
  return (
    <Tag
      ref={ref}
      className={cn('glass', liquid && !dense && 'liquid', strong && 'glass-strong', dense && 'glass-dense', className)}
      {...props}
    />
  )
}
