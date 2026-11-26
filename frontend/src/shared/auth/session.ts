// Tokens ficam em sessionStorage: somem ao fechar a aba e não são compartilhados entre abas.
// Um cookie httpOnly seria mais seguro contra XSS, mas exige mudar o backend; por ora a
// defesa é a política de conteúdo (CSP) e nunca registrar tokens em log.
const TOKEN_KEY = 'educamobile.token'
const REFRESH_KEY = 'educamobile.refresh'
const EXPIRES_KEY = 'educamobile.expires'

export type SessionTokens = { access_token: string; refresh_token: string; expires_in: number }

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY)
}

// Instante (ms) em que o token de acesso vence. Nulo quando só se conhece o token.
export function getExpiresAt(): number | null {
  const raw = sessionStorage.getItem(EXPIRES_KEY)
  return raw === null ? null : Number(raw)
}

export function setToken(t: string): void {
  sessionStorage.setItem(TOKEN_KEY, t)
}

export function saveSession(tokens: SessionTokens): void {
  sessionStorage.setItem(TOKEN_KEY, tokens.access_token)
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token)
  sessionStorage.setItem(EXPIRES_KEY, String(Date.now() + tokens.expires_in * 1000))
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(REFRESH_KEY)
  sessionStorage.removeItem(EXPIRES_KEY)
}
