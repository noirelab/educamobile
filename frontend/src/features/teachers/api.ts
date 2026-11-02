import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type ProfessorLer = components['schemas']['ProfessorLer']
type ProfessorCriar = components['schemas']['ProfessorCriar']
type EscolaLer = components['schemas']['EscolaLer']

type PageParams = { limit: number; offset: number }

export function listTeachers(p: PageParams & { escola_id?: number }) {
  return api<ProfessorLer[]>('/professores', { query: { limit: p.limit, offset: p.offset, escola_id: p.escola_id } })
}

export function getTeacher(id: number) {
  return api<ProfessorLer>(`/professores/${id}`)
}

export function createTeacher(body: ProfessorCriar) {
  return api<ProfessorLer>('/professores', { method: 'POST', json: body })
}

export function updateTeacher(id: number, body: ProfessorCriar) {
  return api<ProfessorLer>(`/professores/${id}`, { method: 'PUT', json: body })
}

export function deleteTeacher(id: number) {
  return api<void>(`/professores/${id}`, { method: 'DELETE' })
}

export function listSchoolsLookup(p: PageParams) {
  return api<EscolaLer[]>('/escolas', { query: { limit: p.limit, offset: p.offset } })
}
