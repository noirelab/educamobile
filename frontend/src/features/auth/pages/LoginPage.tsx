import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Info } from 'lucide-react'
import { ApiError, errorMessage } from '@/shared/api/errors'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { FloatingField } from '@/shared/ui/FloatingField'
import { GlassPanel } from '@/shared/ui/GlassPanel'

function safeNext(value: string | null): string {
  if (!value) return '/'
  if (!value.startsWith('/')) return '/'
  if (value.startsWith('//') || value.startsWith('/\\')) return '/'
  return value
}

function loginError(e: unknown): string {
  if (e instanceof ApiError && e.status === 401) {
    return e.detail || 'E-mail ou senha incorretos'
  }
  return errorMessage(e)
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const expired = searchParams.get('expired') === '1'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(safeNext(searchParams.get('next')), { replace: true })
    } catch (e) {
      setError(loginError(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <GlassPanel strong className="flex w-full max-w-[400px] flex-col p-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-title font-bold text-ink">EducaMobile</h1>
          <p className="text-caption text-ink-muted">Gestão escolar e mobilidade</p>
        </div>

        <div className="mt-6 flex flex-col">
          {expired && (
            <div
              role="status"
              className="mb-4 flex items-center gap-2 rounded-[14px] bg-accent-soft px-3.5 py-3 text-label text-accent"
            >
              <Info size={18} strokeWidth={1.75} aria-hidden="true" className="shrink-0" />
              <p>Sua sessão expirou. Entre novamente</p>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="flex flex-col">
            {error && (
              <div
                role="alert"
                className="mb-4 rounded-[14px] bg-[rgba(220,38,38,0.1)] px-3.5 py-3 text-label text-danger"
              >
                <p>{error}</p>
              </div>
            )}

            <FloatingField
              id="login-email"
              label="E-mail"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />

            <FloatingField
              id="login-password"
              label="Senha"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              trailing={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-11 w-11 hover:translate-y-0"
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </Button>
              }
            />

            <div className="mt-2">
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? 'Entrando…' : 'Entrar'}
              </Button>
            </div>
          </form>
        </div>
      </GlassPanel>
    </main>
  )
}
