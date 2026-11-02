import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type ParadaLer = components['schemas']['ParadaLer']
type ParadaCriar = components['schemas']['ParadaCriar']
type ParadaAtualizar = components['schemas']['ParadaAtualizar']
type ParadaProxima = components['schemas']['ParadaProxima']
type EstudanteDaParada = components['schemas']['EstudanteDaParada']
type EstudanteLer = components['schemas']['EstudanteLer']

type PageParams = { limit: number; offset: number }
type NearbyParams = { latitude: number; longitude: number; raio_m: number; limit: number }

export function listStops(p: PageParams) {
  return api<ParadaLer[]>('/paradas', { query: { limit: p.limit, offset: p.offset } })
}

export function getStop(id: number) {
  return api<ParadaLer>(`/paradas/${id}`)
}

export function createStop(body: ParadaCriar) {
  return api<ParadaLer>('/paradas', { method: 'POST', json: body })
}

export function patchStop(id: number, body: ParadaAtualizar) {
  return api<ParadaLer>(`/paradas/${id}`, { method: 'PATCH', json: body })
}

export function deleteStop(id: number) {
  return api<void>(`/paradas/${id}`, { method: 'DELETE' })
}

export function nearbyStops(p: NearbyParams) {
  return api<ParadaProxima[]>('/paradas/proximas', {
    query: { latitude: p.latitude, longitude: p.longitude, raio_m: p.raio_m, limit: p.limit },
  })
}

export function listStopStudents(id: number) {
  return api<EstudanteDaParada[]>(`/paradas/${id}/estudantes`)
}

export function attachStudent(stopId: number, studentId: number) {
  return api<void>(`/paradas/${stopId}/estudantes/${studentId}`, { method: 'PUT' })
}

export function detachStudent(stopId: number, studentId: number) {
  return api<void>(`/paradas/${stopId}/estudantes/${studentId}`, { method: 'DELETE' })
}

export function listStudents(p: PageParams) {
  return api<EstudanteLer[]>('/estudantes', { query: { limit: p.limit, offset: p.offset } })
}
