import { describe, expect, it } from 'vitest'
import type { components } from '@/shared/api/schema'
import { groupLabel, infrequencyTone, summarize, topByRate } from './summary'

type FrequenciaAgregada = components['schemas']['FrequenciaAgregada']

function row(overrides: Partial<FrequenciaAgregada>): FrequenciaAgregada {
  return {
    grupo_id: 1,
    grupo_nome: 'Grupo',
    total_registros: 0,
    presencas: 0,
    faltas: 0,
    taxa_infrequencia: 0,
    ...overrides,
  }
}

describe('summarize', () => {
  it('sums the rows and computes the absence rate', () => {
    const rows = [
      row({ total_registros: 40, presencas: 31, faltas: 9 }),
      row({ total_registros: 15, presencas: 15, faltas: 0 }),
    ]

    const summary = summarize(rows)

    expect(summary.total_registros).toBe(55)
    expect(summary.presencas).toBe(46)
    expect(summary.faltas).toBe(9)
    expect(summary.taxa).toBeCloseTo(9 / 55)
  })

  it('returns zero rate when there are no records', () => {
    expect(summarize([])).toEqual({ total_registros: 0, presencas: 0, faltas: 0, taxa: 0 })
  })
})

describe('groupLabel', () => {
  it('uses the pole name for polo grouping', () => {
    expect(groupLabel(row({ grupo_nome: 'Polo Centro' }), 'polo')).toBe('Polo Centro')
  })

  it('falls back to "Sem polo" when a polo row has no name', () => {
    expect(groupLabel(row({ grupo_id: null, grupo_nome: null }), 'polo')).toBe('Sem polo')
  })

  it('falls back to "Sem nome" for other groupings without a name', () => {
    expect(groupLabel(row({ grupo_id: null, grupo_nome: null }), 'escola')).toBe('Sem nome')
  })
})

describe('topByRate', () => {
  it('sorts by rate descending, breaking ties by absences', () => {
    const rows = [
      row({ grupo_id: 1, taxa_infrequencia: 0.1, faltas: 2 }),
      row({ grupo_id: 2, taxa_infrequencia: 0.3, faltas: 1 }),
      row({ grupo_id: 3, taxa_infrequencia: 0.3, faltas: 5 }),
    ]

    expect(topByRate(rows).map((r) => r.grupo_id)).toEqual([3, 2, 1])
  })

  it('limits the result to n rows and does not mutate the input', () => {
    const rows = [
      row({ grupo_id: 1, taxa_infrequencia: 0.1 }),
      row({ grupo_id: 2, taxa_infrequencia: 0.2 }),
      row({ grupo_id: 3, taxa_infrequencia: 0.3 }),
    ]

    expect(topByRate(rows, 2).map((r) => r.grupo_id)).toEqual([3, 2])
    expect(rows.map((r) => r.grupo_id)).toEqual([1, 2, 3])
  })
})

describe('infrequencyTone', () => {
  it('is danger from 40 percent, warning from 20 percent, default below', () => {
    expect(infrequencyTone(0.4)).toBe('danger')
    expect(infrequencyTone(0.2)).toBe('warning')
    expect(infrequencyTone(0.19)).toBe('default')
  })
})
