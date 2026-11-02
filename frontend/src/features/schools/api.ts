import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type EscolaLer = components['schemas']['EscolaLer']
type EscolaCriar = components['schemas']['EscolaCriar']
type PoloLer = components['schemas']['PoloLer']
type TurmaLer = components['schemas']['TurmaLer']
type ProfessorLer = components['schemas']['ProfessorLer']
type FrequenciaAgregada = components['schemas']['FrequenciaAgregada']

type PageParams = { limit: number; offset: number }

export function listSchools(p: PageParams & { polo_id?: number }) {
  return api<EscolaLer[]>('/escolas', { query: { limit: p.limit, offset: p.offset, polo_id: p.polo_id } })
}

export function getSchool(id: number) {
  return api<EscolaLer>(`/escolas/${id}`)
}

export function createSchool(body: EscolaCriar) {
  return api<EscolaLer>('/escolas', { method: 'POST', json: body })
}

export function updateSchool(id: number, body: EscolaCriar) {
  return api<EscolaLer>(`/escolas/${id}`, { method: 'PUT', json: body })
}

export function deleteSchool(id: number) {
  return api<void>(`/escolas/${id}`, { method: 'DELETE' })
}

export function listPolesLookup(p: PageParams) {
  return api<PoloLer[]>('/polos', { query: { limit: p.limit, offset: p.offset } })
}

export function listClassesBySchool(schoolId: number, p: PageParams) {
  return api<TurmaLer[]>('/turmas', { query: { escola_id: schoolId, limit: p.limit, offset: p.offset } })
}

export function listTeachersBySchool(schoolId: number, p: PageParams) {
  return api<ProfessorLer[]>('/professores', { query: { escola_id: schoolId, limit: p.limit, offset: p.offset } })
}

export function listClassAttendance(p: { data_inicio: string; data_fim: string }) {
  return api<FrequenciaAgregada[]>('/frequencias/agregada', {
    query: { agrupar: 'turma', data_inicio: p.data_inicio, data_fim: p.data_fim },
  })
}
