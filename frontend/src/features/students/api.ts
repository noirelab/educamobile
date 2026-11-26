import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type EstudanteLer = components['schemas']['EstudanteLer']
type EstudantesPagina = components['schemas']['EstudantesPagina']
type EstudanteCriar = components['schemas']['EstudanteCriar']
type ParadaLer = components['schemas']['ParadaLer']

type ListParams = { limit: number; offset: number; q?: string }

export function listStudents(p: ListParams) {
  return api<EstudantesPagina>('/estudantes', { query: { limit: p.limit, offset: p.offset, q: p.q || undefined } })
}

export function getStudent(id: number) {
  return api<EstudanteLer>(`/estudantes/${id}`)
}

export function createStudent(body: EstudanteCriar) {
  return api<EstudanteLer>('/estudantes', { method: 'POST', json: body })
}

export function updateStudent(id: number, body: EstudanteCriar) {
  return api<EstudanteLer>(`/estudantes/${id}`, { method: 'PUT', json: body })
}

export function deleteStudent(id: number) {
  return api<void>(`/estudantes/${id}`, { method: 'DELETE' })
}

export function listStopOptions() {
  return api<ParadaLer[]>('/paradas', { query: { limit: 200 } })
}
