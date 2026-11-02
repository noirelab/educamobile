import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type RotaLer = components['schemas']['RotaLer']
type RotaCriar = components['schemas']['RotaCriar']
type RotaAtualizar = components['schemas']['RotaAtualizar']
type RotaSequencia = components['schemas']['RotaSequencia']
type ParadaLer = components['schemas']['ParadaLer']

type PageParams = { limit: number; offset: number }

export function listRoutes(p: PageParams) {
  return api<RotaLer[]>('/rotas', { query: { limit: p.limit, offset: p.offset } })
}

export function getRoute(id: number) {
  return api<RotaLer>(`/rotas/${id}`)
}

export function createRoute(body: RotaCriar) {
  return api<RotaLer>('/rotas', { method: 'POST', json: body })
}

export function renameRoute(id: number, body: RotaAtualizar) {
  return api<RotaLer>(`/rotas/${id}`, { method: 'PATCH', json: body })
}

export function setRouteStops(id: number, body: RotaSequencia) {
  return api<RotaLer>(`/rotas/${id}/paradas`, { method: 'PUT', json: body })
}

export function deleteRoute(id: number) {
  return api<void>(`/rotas/${id}`, { method: 'DELETE' })
}

export function listEditorStops() {
  return api<ParadaLer[]>('/paradas', { query: { limit: 500 } })
}
