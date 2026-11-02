import type { components } from '@/shared/api/schema'
import { errorMessage } from '@/shared/api/errors'

type MatriculaLer = components['schemas']['MatriculaLer']
type FrequenciaLer = components['schemas']['FrequenciaLer']

export type RollEntry = { matricula_id: number; presente: boolean; saved: boolean }

export function activeOn(m: MatriculaLer, day: string): boolean {
  if (m.data_inicio > day) return false
  if (m.data_fim === null) return true
  if (m.status === 'transferida') return day < m.data_fim
  return day <= m.data_fim
}

export function buildRoll(enrollments: MatriculaLer[], existing: FrequenciaLer[], day: string): RollEntry[] {
  const savedByMatricula = new Map(
    existing.filter((registro) => registro.data === day).map((registro) => [registro.matricula_id, registro.presente]),
  )
  return enrollments
    .filter((m) => activeOn(m, day))
    .map((m) => ({
      matricula_id: m.id,
      presente: savedByMatricula.get(m.id) ?? true,
      saved: savedByMatricula.has(m.id),
    }))
}

export function rollErrorMessage(error: unknown, nameOf: (matriculaId: number) => string | undefined): string {
  const message = errorMessage(error)
  const match = /matrícula (\d+)/.exec(message)
  const name = match ? nameOf(Number(match[1])) : undefined
  return name ? `${name}: ${message}` : message
}
