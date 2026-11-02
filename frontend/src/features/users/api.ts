import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type UsuarioCriar = components['schemas']['UsuarioCriar']
type UsuarioLer = components['schemas']['UsuarioLer']
type EscolaLer = components['schemas']['EscolaLer']

type PageParams = { limit: number; offset: number }

export function createUser(body: UsuarioCriar): Promise<UsuarioLer> {
  return api<UsuarioLer>('/auth/usuarios', { method: 'POST', json: body })
}

export function listSchoolsLookup(p: PageParams) {
  return api<EscolaLer[]>('/escolas', { query: { limit: p.limit, offset: p.offset } })
}

export function getSchool(id: number) {
  return api<EscolaLer>(`/escolas/${id}`)
}
