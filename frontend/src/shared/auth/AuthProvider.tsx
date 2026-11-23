import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { onUnauthorized } from '@/shared/api/client'
import { loginRequest, logoutAllRequest, logoutRequest, meRequest } from '@/features/auth/api'
import { clearToken, getRefreshToken, getToken, saveSession } from '@/shared/auth/session'
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
    saveSession(token)
    setUser(await meRequest())
  }, [])

  const endSession = useCallback(() => {
    clearToken()
    queryClient.clear()
    setUser(null)
    navigate('/login')
  }, [navigate, queryClient])

  // A sessão local sempre termina, mesmo que o aviso ao servidor falhe (sem rede, por exemplo).
  const logout = useCallback(() => {
    const refresh = getRefreshToken()
    const aviso = refresh ? logoutRequest(refresh).catch(() => undefined) : Promise.resolve()
    void aviso.finally(endSession)
  }, [endSession])

  const logoutAll = useCallback(() => {
    void logoutAllRequest()
      .catch(() => undefined)
      .finally(endSession)
  }, [endSession])

  const value = useMemo<AuthState>(
    () => ({ user, role: user?.perfil ?? null, login, logout, logoutAll, ready }),
    [user, login, logout, logoutAll, ready],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
