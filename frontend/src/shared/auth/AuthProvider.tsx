import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { onUnauthorized } from '@/shared/api/client'
import { loginRequest, meRequest } from '@/features/auth/api'
import { clearToken, getToken, setToken } from '@/shared/auth/session'
import { AuthContext, type AuthState, type Usuario } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [user, setUser] = useState<Usuario | null>(null)
  const [ready, setReady] = useState(false)

  const current = location.pathname + location.search

  useEffect(() => {
    onUnauthorized(() => {
      clearToken()
      queryClient.clear()
      flushSync(() => setUser(null))
      navigate(`/login?expired=1&next=${encodeURIComponent(current)}`)
    })
  }, [navigate, queryClient, current])

  useEffect(() => {
    if (!getToken()) {
      setReady(true)
      return
    }
    meRequest()
      .then(setUser)
      .catch(() => {
        clearToken()
        setUser(null)
      })
      .finally(() => setReady(true))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const token = await loginRequest(email, password)
    setToken(token.access_token)
    setUser(await meRequest())
  }, [])

  const logout = useCallback(() => {
    clearToken()
    queryClient.clear()
    setUser(null)
    navigate('/login')
  }, [navigate, queryClient])

  const value = useMemo<AuthState>(
    () => ({ user, role: user?.perfil ?? null, login, logout, ready }),
    [user, login, logout, ready],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
