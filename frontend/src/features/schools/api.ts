import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type EscolaLer = components['schemas']['EscolaLer']
type EscolaCriar = components['schemas']['EscolaCriar']

type PageParams = { limit: number; offset: number }

export function listSchools(p: PageParams) {
  return api<EscolaLer[]>('/escolas', { query: { limit: p.limit, offset: p.offset } })
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
