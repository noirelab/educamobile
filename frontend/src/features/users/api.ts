import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type UsuarioCriar = components['schemas']['UsuarioCriar']
type UsuarioLer = components['schemas']['UsuarioLer']

export function createUser(body: UsuarioCriar): Promise<UsuarioLer> {
  return api<UsuarioLer>('/usuarios', { method: 'POST', json: body })
}

export function changePassword(body: { senha_atual: string; senha_nova: string }): Promise<void> {
  return api<void>('/auth/senha', { method: 'PUT', json: body })
}
