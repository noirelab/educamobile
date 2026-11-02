import type { FrequenciaAgregada, Group } from './api'

export type Summary = { total_registros: number; presencas: number; faltas: number; taxa: number }

export function summarize(rows: FrequenciaAgregada[]): Summary {
  const total_registros = rows.reduce((sum, row) => sum + row.total_registros, 0)
  const presencas = rows.reduce((sum, row) => sum + row.presencas, 0)
  const faltas = rows.reduce((sum, row) => sum + row.faltas, 0)
  const taxa = total_registros === 0 ? 0 : faltas / total_registros
  return { total_registros, presencas, faltas, taxa }
}

export type KpiTone = 'default' | 'warning' | 'danger'

export function infrequencyTone(rate: number): KpiTone {
  if (rate >= 0.4) return 'danger'
  if (rate >= 0.2) return 'warning'
  return 'default'
}

export function groupLabel(row: FrequenciaAgregada, group: Group): string {
  if (row.grupo_nome !== null) return row.grupo_nome
  return group === 'polo' ? 'Sem polo' : 'Sem nome'
}

export function topByRate(rows: FrequenciaAgregada[], n = 10): FrequenciaAgregada[] {
  return [...rows]
    .sort((a, b) => b.taxa_infrequencia - a.taxa_infrequencia || b.faltas - a.faltas)
    .slice(0, n)
}
