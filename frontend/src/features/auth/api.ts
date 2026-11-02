import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'
import type { Usuario } from '@/shared/auth/AuthContext'

export type Token = components['schemas']['Token']

export function loginRequest(email: string, password: string): Promise<Token> {
  const form = new URLSearchParams({ username: email, password })
  return api<Token>('/auth/login', { method: 'POST', form })
}

export function meRequest(): Promise<Usuario> {
  return api<Usuario>('/auth/me')
}
