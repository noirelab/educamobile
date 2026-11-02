const TOKEN_KEY = 'educamobile.token'

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(t: string): void {
  sessionStorage.setItem(TOKEN_KEY, t)
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}
