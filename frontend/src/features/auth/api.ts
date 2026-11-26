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

// Encerra só a sessão deste aparelho. O backend responde 204 mesmo para token desconhecido.
export function logoutRequest(refreshToken: string): Promise<void> {
  return api<void>('/auth/logout', { method: 'POST', json: { refresh_token: refreshToken } })
}

// Encerra todas as sessões da conta, por exemplo depois de perder o celular.
export function logoutAllRequest(): Promise<void> {
  return api<void>('/auth/logout-todos', { method: 'POST' })
}
