export class ApiError extends Error {
  status: number
  detail: string
  fieldErrors: Record<string, string>

  constructor(status: number, detail: string, fieldErrors: Record<string, string> = {}) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.fieldErrors = fieldErrors
  }
}

type ValidationItem = { loc?: unknown[]; msg?: unknown }

export function toApiError(status: number, body: unknown): ApiError {
  const raw = typeof body === 'object' && body !== null ? (body as { detail?: unknown }).detail : undefined

  if (typeof raw === 'string') {
    return new ApiError(status, raw)
  }

  if (Array.isArray(raw)) {
    const fieldErrors: Record<string, string> = {}
    let first = ''
    for (const item of raw as ValidationItem[]) {
      const msg = typeof item.msg === 'string' ? item.msg : ''
      const loc = Array.isArray(item.loc) ? item.loc : []
      const field = loc.length > 0 ? String(loc[loc.length - 1]) : ''
      if (field && msg) fieldErrors[field] = msg
      if (!first && msg) first = msg
    }
    return new ApiError(status, first, fieldErrors)
  }

  return new ApiError(status, '')
}

export function errorMessage(e: unknown): string {
  if (!(e instanceof ApiError)) return 'Erro inesperado. Tente novamente'
  switch (e.status) {
    case 0:
      return 'Não foi possível conectar ao servidor'
    case 401:
      return 'Sessão expirada. Entre novamente'
    case 403:
      return 'Você não tem permissão para esta ação'
    case 404:
      return 'Registro não encontrado'
    case 429:
      return 'Muitas tentativas. Tente novamente em 15 minutos'
    case 409:
    case 422:
      if (e.detail) return e.detail
      return 'Erro inesperado. Tente novamente'
    default:
      return 'Erro inesperado. Tente novamente'
  }
}
