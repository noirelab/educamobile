import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { useLiquidGlass } from '@/shared/ui/useLiquidGlass'
import { Skeleton } from '@/shared/ui/Skeleton'

type KpiTone = 'default' | 'warning' | 'danger'

type KpiCardProps = {
  label: string
  value: ReactNode
  icon?: LucideIcon
  tone?: KpiTone
  loading?: boolean
}

const toneClass: Record<KpiTone, string> = {
  default: 'text-ink',
  warning: 'text-warning-text',
  danger: 'text-danger',
}

export function KpiCard({ label, value, icon: Icon, tone = 'default', loading = false }: KpiCardProps) {
  const ref = useLiquidGlass<HTMLDivElement>(true, 22, true)
  return (
    <div
      ref={ref}
      className="glass liquid lift flex min-h-[104px] flex-col justify-between gap-2 p-[18px]"
      data-tone={tone}
      aria-busy={loading || undefined}
    >
      <div className="flex items-center gap-2 text-label text-ink-muted">
        {Icon && <Icon size={16} strokeWidth={1.75} aria-hidden="true" />}
        <span>{label}</span>
      </div>
      {loading ? (
        <Skeleton className="h-[28px] w-24" />
      ) : (
        <div className={cn('text-display font-bold tabular-nums', toneClass[tone])}>{value}</div>
      )}
    </div>
  )
}
