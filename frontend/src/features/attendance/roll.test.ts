import { describe, expect, it } from 'vitest'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { activeOn, buildRoll, rollErrorMessage } from './roll'

type MatriculaLer = components['schemas']['MatriculaLer']
type FrequenciaLer = components['schemas']['FrequenciaLer']

function matricula(overrides: Partial<MatriculaLer>): MatriculaLer {
  return { id: 1, estudante_id: 1, turma_id: 1, data_inicio: '2026-02-01', data_fim: null, status: 'ativa', ...overrides }
}

describe('activeOn', () => {
  it('is true on the start day', () => {
    expect(activeOn(matricula({ data_inicio: '2026-02-01' }), '2026-02-01')).toBe(true)
  })

  it('is false before the start day', () => {
    expect(activeOn(matricula({ data_inicio: '2026-02-01' }), '2026-01-31')).toBe(false)
  })

  it('is false on the transfer day for a transferida enrollment', () => {
    const transferida = matricula({ status: 'transferida', data_fim: '2026-03-10' })
    expect(activeOn(transferida, '2026-03-10')).toBe(false)
    expect(activeOn(transferida, '2026-03-09')).toBe(true)
  })

  it('is true on the close day for an encerrada enrollment', () => {
    expect(activeOn(matricula({ status: 'encerrada', data_fim: '2026-03-10' }), '2026-03-10')).toBe(true)
    expect(activeOn(matricula({ status: 'encerrada', data_fim: '2026-03-10' }), '2026-03-11')).toBe(false)
  })
})

describe('buildRoll', () => {
  it('defaults to presente and unsaved, and skips enrollments not active on the day', () => {
    const enrollments = [
      matricula({ id: 1 }),
      matricula({ id: 2, status: 'encerrada', data_fim: '2026-02-10' }),
    ]

    expect(buildRoll(enrollments, [], '2026-02-20')).toEqual([{ matricula_id: 1, presente: true, saved: false }])
  })

  it('uses the existing record of the day and marks it as saved', () => {
    const existing: FrequenciaLer[] = [{ id: 9, matricula_id: 1, data: '2026-02-20', presente: false }]

    expect(buildRoll([matricula({ id: 1 })], existing, '2026-02-20')).toEqual([
      { matricula_id: 1, presente: false, saved: true },
    ])
  })

  it('ignores existing records from other days', () => {
    const existing: FrequenciaLer[] = [{ id: 9, matricula_id: 1, data: '2026-02-19', presente: false }]

    expect(buildRoll([matricula({ id: 1 })], existing, '2026-02-20')).toEqual([
      { matricula_id: 1, presente: true, saved: false },
    ])
  })
})

describe('rollErrorMessage', () => {
  it('prefixes the student name when the error names the enrollment', () => {
    const error = new ApiError(422, 'Data fora do período da matrícula 2')
    const nameOf = (id: number) => (id === 2 ? 'Bruno Lima' : undefined)

    expect(rollErrorMessage(error, nameOf)).toBe('Bruno Lima: Data fora do período da matrícula 2')
  })

  it('returns the plain message when no student matches', () => {
    const error = new ApiError(422, 'Data fora do período da matrícula 7')

    expect(rollErrorMessage(error, () => undefined)).toBe('Data fora do período da matrícula 7')
  })
})
