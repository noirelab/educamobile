import { getToken } from '@/shared/auth/session'
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

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
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

  let response: Response
  try {
    response = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? 'GET',
      headers,
      body,
    })
  } catch {
    throw new ApiError(0, '')
  }

  if (response.status === 401 && path !== LOGIN_PATH) {
    unauthorizedHandler?.()
  }

  if (!response.ok) {
    throw toApiError(response.status, await parseBody(response))
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
