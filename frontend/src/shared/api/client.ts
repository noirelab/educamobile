import { clearToken, getExpiresAt, getRefreshToken, getToken, saveSession, type SessionTokens } from '@/shared/auth/session'
import { ApiError, toApiError } from '@/shared/api/errors'

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
type QueryValue = string | number | boolean | undefined

export type ApiOptions = {
  method?: Method
  query?: Record<string, QueryValue>
  json?: unknown
  form?: URLSearchParams
}

const LOGIN_PATH = '/auth/login'
const REFRESH_PATH = '/auth/refresh'
// Rotas que não usam o token de acesso: um 401 nelas não significa sessão vencida.
const PUBLIC_PATHS = new Set([LOGIN_PATH, REFRESH_PATH, '/auth/logout'])
// Renova um pouco antes de vencer, para a requisição não sair com um token quase morto.
const RENEW_MARGIN_MS = 30_000

let unauthorizedHandler: (() => void) | null = null

export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) params.set(key, String(value))
  }
  const qs = params.toString()
  return `${base}${path}${qs ? `?${qs}` : ''}`
}

async function parseBody(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return undefined
  }
}

// Uma renovação por vez: o backend trata o reuso de um refresh token como roubo e derruba
// todas as sessões, então duas renovações simultâneas com o mesmo token seriam um desastre.
let renewing: Promise<boolean> | null = null

function renewSession(): Promise<boolean> {
  renewing ??= doRenew().finally(() => {
    renewing = null
  })
  return renewing
}

async function doRenew(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  let response: Response
  try {
    response = await fetch(buildUrl(REFRESH_PATH), {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
  } catch {
    // Sem rede não dá para saber se a sessão vale: mantém os tokens e deixa a requisição falhar.
    return false
  }
  if (!response.ok) {
    clearToken()
    return false
  }
  saveSession((await response.json()) as SessionTokens)
  return true
}

function expiresSoon(): boolean {
  const expiresAt = getExpiresAt()
  return expiresAt !== null && expiresAt - Date.now() < RENEW_MARGIN_MS
}

function send(path: string, opts: ApiOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let body: string | undefined
  if (opts.form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    body = opts.form.toString()
  } else if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.json)
  }

  return fetch(buildUrl(path, opts.query), { method: opts.method ?? 'GET', headers, body })
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const isPublic = PUBLIC_PATHS.has(path)
  if (!isPublic && expiresSoon()) await renewSession()

  let response: Response
  try {
    response = await send(path, opts)
    // Token recusado: renova uma única vez e repete a requisição.
    if (response.status === 401 && !isPublic && getRefreshToken() && (await renewSession())) {
      response = await send(path, opts)
    }
  } catch {
    throw new ApiError(0, '')
  }

  if (response.status === 401 && !isPublic) {
    unauthorizedHandler?.()
  }

  if (!response.ok) {
    throw toApiError(response.status, await parseBody(response))
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
