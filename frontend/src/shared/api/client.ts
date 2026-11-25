import { clearToken, getExpiresAt, getRefreshToken, getToken, saveSession, type SessionTokens } from '@/shared/auth/session'
import { z } from 'zod'
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
// ok: tokens novos. expired: a sessão acabou (401). unavailable: sem rede, 429 ou 5xx, e a
// sessão pode continuar valendo.
type Renewal = 'ok' | 'expired' | 'unavailable'
let renewing: Promise<Renewal> | null = null

function renewSession(): Promise<Renewal> {
  renewing ??= renewAcrossTabs().finally(() => {
    renewing = null
  })
  return renewing
}

// "Duplicar aba" copia o sessionStorage: as duas abas ficam com o mesmo refresh token. A trava
// do navegador põe as renovações das abas em fila, e a aba que renova manda o par novo às que
// tinham o mesmo token, que passam a usá-lo em vez de reapresentar o antigo.
const LOCK_NAME = 'educamobile.renovar'
// Dá tempo de a mensagem da aba que acabou de renovar chegar antes de conferir o token.
const BROADCAST_WAIT_MS = 50
const rotationSchema = z.object({
  previous: z.string().min(1),
  tokens: z.object({
    access_token: z.string().min(1),
    refresh_token: z.string().min(1),
    expires_in: z.number().positive(),
  }),
})
type Rotation = z.infer<typeof rotationSchema>
const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('educamobile.sessao')
channel?.addEventListener('message', (event: MessageEvent<unknown>) => {
  const rotation = rotationSchema.safeParse(event.data)
  if (rotation.success && rotation.data.previous === getRefreshToken()) saveSession(rotation.data.tokens)
})

async function renewAcrossTabs(): Promise<Renewal> {
  const refresh = getRefreshToken()
  if (!refresh) return 'expired'
  const locks = typeof navigator === 'undefined' ? undefined : navigator.locks
  if (!locks || !channel) return doRenew(refresh)
  return locks.request(LOCK_NAME, async () => {
    await new Promise((resolve) => setTimeout(resolve, BROADCAST_WAIT_MS))
    const current = getRefreshToken()
    // Outra aba já renovou este token e repassou o par novo.
    if (current !== refresh) return current === null ? 'expired' : 'ok'
    return doRenew(refresh)
  })
}

async function doRenew(refresh: string): Promise<Renewal> {
  let response: Response
  try {
    response = await fetch(buildUrl(REFRESH_PATH), {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
  } catch {
    // Sem rede não dá para saber se a sessão vale: mantém os tokens e deixa a requisição falhar.
    return 'unavailable'
  }
  if (!response.ok) {
    // Só o 401 diz que a sessão acabou. Com 429 ou 5xx (API instável) os tokens continuam.
    if (response.status !== 401) return 'unavailable'
    clearToken()
    return 'expired'
  }
  const tokens = (await response.json()) as SessionTokens
  saveSession(tokens)
  channel?.postMessage({ previous: refresh, tokens } satisfies Rotation)
  return 'ok'
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
  let renewal: Renewal | null = null
  try {
    response = await send(path, opts)
    // Token recusado: renova uma única vez e repete a requisição.
    if (response.status === 401 && !isPublic && getRefreshToken()) {
      renewal = await renewSession()
      if (renewal === 'ok') response = await send(path, opts)
    }
  } catch {
    throw new ApiError(0, '')
  }

  if (response.status === 401 && !isPublic) {
    // A renovação falhou por instabilidade da API, não porque a sessão acabou: não desloga.
    if (renewal === 'unavailable') throw new ApiError(0, '')
    unauthorizedHandler?.()
  }

  if (!response.ok) {
    throw toApiError(response.status, await parseBody(response))
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
