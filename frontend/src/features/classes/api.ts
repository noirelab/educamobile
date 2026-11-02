import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type TurmaLer = components['schemas']['TurmaLer']
type TurmaCriar = components['schemas']['TurmaCriar']
type EscolaLer = components['schemas']['EscolaLer']
type MatriculaLer = components['schemas']['MatriculaLer']
type EstudanteLer = components['schemas']['EstudanteLer']

type PageParams = { limit: number; offset: number }

export function listClasses(p: PageParams & { escola_id?: number }) {
  return api<TurmaLer[]>('/turmas', { query: { limit: p.limit, offset: p.offset, escola_id: p.escola_id } })
}

export function getClass(id: number) {
  return api<TurmaLer>(`/turmas/${id}`)
}

export function createClass(body: TurmaCriar) {
  return api<TurmaLer>('/turmas', { method: 'POST', json: body })
}

export function updateClass(id: number, body: TurmaCriar) {
  return api<TurmaLer>(`/turmas/${id}`, { method: 'PUT', json: body })
}

export function deleteClass(id: number) {
  return api<void>(`/turmas/${id}`, { method: 'DELETE' })
}

export function listSchoolsLookup(p: PageParams) {
  return api<EscolaLer[]>('/escolas', { query: { limit: p.limit, offset: p.offset } })
}

export function listActiveEnrollments(turmaId: number, p: PageParams) {
  return api<MatriculaLer[]>('/matriculas', {
    query: { turma_id: turmaId, status: 'ativa', limite: p.limit, deslocamento: p.offset },
  })
}

export function getStudent(id: number) {
  return api<EstudanteLer>(`/estudantes/${id}`)
}
