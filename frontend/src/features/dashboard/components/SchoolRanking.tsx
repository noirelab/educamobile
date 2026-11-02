import { Link } from 'react-router-dom'
import { formatPercent } from '@/shared/lib/format'
import { rateColor } from '@/shared/lib/heat'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import type { FrequenciaAgregada } from '../api'
import { groupLabel, topByRate } from '../summary'

type SchoolRankingProps = {
  rows: FrequenciaAgregada[]
}

export function SchoolRanking({ rows }: SchoolRankingProps) {
  const top = topByRate(rows, 10)

  return (
    <Panel title="Escolas com mais faltas" className="h-full">
      {rows.length === 0 ? (
        <PageState status="empty" emptyText="Nenhuma escola com registros no período" />
      ) : (
        <ol aria-label="Escolas com mais faltas" className="flex flex-col divide-y divide-line">
          {top.map((row, index) => (
            <li key={row.grupo_id ?? index} className="flex items-center gap-3 py-2.5 text-body">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-caption font-semibold text-accent">
                {index + 1}
              </span>
              {row.grupo_id !== null ? (
                <Link
                  to={`/schools/${row.grupo_id}`}
                  className="focus-ring min-w-0 flex-1 truncate rounded-md font-medium text-ink underline-offset-4 hover:underline"
                >
                  {groupLabel(row, 'escola')}
                </Link>
              ) : (
                <span className="min-w-0 flex-1 truncate text-ink">{groupLabel(row, 'escola')}</span>
              )}
              <span className="shrink-0 text-caption tabular-nums text-ink-muted">
                {row.faltas}/{row.total_registros}
              </span>
              <span className="flex shrink-0 items-center gap-1.5 font-semibold tabular-nums text-ink">
                <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: rateColor(row.taxa_infrequencia) }} />
                {formatPercent(row.taxa_infrequencia)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}
