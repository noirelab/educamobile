import { CheckCircle2, ClipboardList, TrendingUp, XCircle } from 'lucide-react'
import { formatPercent } from '@/shared/lib/format'
import { KpiCard } from '@/shared/ui/KpiCard'
import { infrequencyTone, type Summary } from '../summary'

type KpiCardsProps = {
  summary: Summary | undefined
  loading: boolean
}

const count = new Intl.NumberFormat('pt-BR')

export function KpiCards({ summary, loading }: KpiCardsProps) {
  const value = (format: (s: Summary) => string) => (summary ? format(summary) : '—')

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      <KpiCard label="Registros" icon={ClipboardList} loading={loading} value={value((s) => count.format(s.total_registros))} />
      <KpiCard label="Presenças" icon={CheckCircle2} loading={loading} value={value((s) => count.format(s.presencas))} />
      <KpiCard label="Faltas" icon={XCircle} loading={loading} value={value((s) => count.format(s.faltas))} />
      <KpiCard
        label="Infrequência"
        icon={TrendingUp}
        loading={loading}
        tone={summary ? infrequencyTone(summary.taxa) : 'default'}
        value={value((s) => formatPercent(s.taxa))}
      />
    </div>
  )
}
