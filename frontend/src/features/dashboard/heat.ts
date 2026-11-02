import { formatPercent } from '@/shared/lib/format'
import type { Escola, FrequenciaAgregada } from './api'

export function heatPoints(
  schools: Escola[],
  rows: FrequenciaAgregada[],
): { points: [number, number, number][]; missing: number } {
  const byId = new Map(schools.map((school) => [school.id, school]))
  const points: [number, number, number][] = []
  const missingIds = new Set<number>()

  for (const row of rows) {
    if (row.grupo_id === null) continue
    const school = byId.get(row.grupo_id)
    if (!school) continue
    if (school.localizacao == null) {
      missingIds.add(school.id)
      continue
    }
    points.push([school.localizacao.latitude, school.localizacao.longitude, row.taxa_infrequencia])
  }

  return { points, missing: missingIds.size }
}

export function popupLabel(name: string, row: FrequenciaAgregada | undefined): string {
  if (!row) return name
  return `${name} · ${row.faltas}/${row.total_registros} · ${formatPercent(row.taxa_infrequencia)}`
}
