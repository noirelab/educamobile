import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type FrequenciaLer = components['schemas']['FrequenciaLer']
type FrequenciaLote = components['schemas']['FrequenciaLote']
type FrequenciaCriar = components['schemas']['FrequenciaCriar']

export type AttendanceQuery = {
  turma_id?: number
  estudante_id?: number
  matricula_id?: number
  data_inicio?: string
  data_fim?: string
  limite?: number
  deslocamento?: number
}

export function listAttendance(p: AttendanceQuery) {
  return api<FrequenciaLer[]>('/frequencias', {
    query: {
      turma_id: p.turma_id,
      estudante_id: p.estudante_id,
      matricula_id: p.matricula_id,
      data_inicio: p.data_inicio,
      data_fim: p.data_fim,
      limite: p.limite,
      deslocamento: p.deslocamento,
    },
  })
}

export function saveBatch(body: FrequenciaLote) {
  return api<FrequenciaLer[]>('/frequencias/lote', { method: 'POST', json: body })
}

export function saveOne(body: FrequenciaCriar) {
  return api<FrequenciaLer>('/frequencias', { method: 'POST', json: body })
}
