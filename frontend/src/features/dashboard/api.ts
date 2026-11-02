import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type FrequenciaAgregada = components['schemas']['FrequenciaAgregada']

export type Group = components['schemas']['Agrupamento']

export type Escola = components['schemas']['EscolaLer']
export type Polo = components['schemas']['PoloLer']
export type Rota = components['schemas']['RotaLer']
export type Parada = components['schemas']['ParadaLer']

export type AggregateParams = { agrupar: Group; data_inicio: string; data_fim: string }

type PageParams = { limit: number; offset: number }

export function getAggregate(p: AggregateParams) {
  return api<FrequenciaAgregada[]>('/frequencias/agregada', {
    query: { agrupar: p.agrupar, data_inicio: p.data_inicio, data_fim: p.data_fim },
  })
}

export function listEscolas(p: PageParams) {
  return api<Escola[]>('/escolas', { query: { limit: p.limit, offset: p.offset } })
}

export function listPolos(p: PageParams) {
  return api<Polo[]>('/polos', { query: { limit: p.limit, offset: p.offset } })
}

export function listRotas(p: PageParams) {
  return api<Rota[]>('/rotas', { query: { limit: p.limit, offset: p.offset } })
}

export function listParadas(p: PageParams) {
  return api<Parada[]>('/paradas', { query: { limit: p.limit, offset: p.offset } })
}
