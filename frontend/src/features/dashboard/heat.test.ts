import { describe, expect, it } from 'vitest'
import type { components } from '@/shared/api/schema'
import type { FrequenciaAgregada } from './api'
import { heatPoints } from './heat'

type EscolaLer = components['schemas']['EscolaLer']

const LOCATION = { latitude: -25.43, longitude: -49.27 }

function school(id: number, nome: string, localizacao: EscolaLer['localizacao'] | null = LOCATION): EscolaLer {
  return { id, nome, codigo_inep: null, endereco: null, polo_id: null, localizacao: localizacao as EscolaLer['localizacao'] }
}

function row(grupo_id: number | null, taxa: number): FrequenciaAgregada {
  return { grupo_id, grupo_nome: 'x', total_registros: 10, presencas: 10 - taxa * 10, faltas: taxa * 10, taxa_infrequencia: taxa }
}

describe('heatPoints', () => {
  it('joins rows to schools by grupo_id and uses the rate as weight', () => {
    const schools = [school(1, 'A'), school(2, 'B')]
    const result = heatPoints(schools, [row(2, 0.25), row(1, 0.1)])

    expect(result.points).toEqual([
      [LOCATION.latitude, LOCATION.longitude, 0.25],
      [LOCATION.latitude, LOCATION.longitude, 0.1],
    ])
    expect(result.missing).toBe(0)
  })

  it('ignores rows without a matching school or without grupo_id', () => {
    const result = heatPoints([school(1, 'A')], [row(99, 0.5), row(null, 0.5), row(1, 0.2)])

    expect(result.points).toHaveLength(1)
    expect(result.points[0]).toEqual([LOCATION.latitude, LOCATION.longitude, 0.2])
  })

  it('counts matched schools that have no location as missing', () => {
    const schools = [school(1, 'A', null), school(2, 'B')]
    const result = heatPoints(schools, [row(1, 0.3), row(2, 0.1)])

    expect(result.points).toEqual([[LOCATION.latitude, LOCATION.longitude, 0.1]])
    expect(result.missing).toBe(1)
  })
})
