import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type PoloLer = components['schemas']['PoloLer']
type PoloCriar = components['schemas']['PoloCriar']
type EscolaLer = components['schemas']['EscolaLer']

type PageParams = { limit: number; offset: number }

export function listPoles(p: PageParams) {
  return api<PoloLer[]>('/polos', { query: { limit: p.limit, offset: p.offset } })
}

export function getPole(id: number) {
  return api<PoloLer>(`/polos/${id}`)
}

export function createPole(body: PoloCriar) {
  return api<PoloLer>('/polos', { method: 'POST', json: body })
}

export function updatePole(id: number, body: PoloCriar) {
  return api<PoloLer>(`/polos/${id}`, { method: 'PUT', json: body })
}

export function deletePole(id: number) {
  return api<void>(`/polos/${id}`, { method: 'DELETE' })
}

export function listSchoolsInArea(id: number) {
  return api<EscolaLer[]>(`/polos/${id}/escolas-na-area`)
}

export function listSchoolsByPole(poleId: number, p: PageParams) {
  return api<EscolaLer[]>('/escolas', { query: { polo_id: poleId, limit: p.limit, offset: p.offset } })
}
