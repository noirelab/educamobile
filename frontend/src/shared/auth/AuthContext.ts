import { createContext } from 'react'
import type { components } from '@/shared/api/schema'
import type { Role } from './permissions'

export type Usuario = components['schemas']['UsuarioLer']

export type AuthState = {
  user: Usuario | null
  role: Role | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  ready: boolean
}

export const AuthContext = createContext<AuthState | null>(null)
