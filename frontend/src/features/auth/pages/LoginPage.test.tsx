import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import { LoginPage } from './LoginPage'

const API = 'http://api.test'

afterEach(cleanup)

const usuario = {
  id: 1,
  nome: 'Ana',
  email: 'ana@educa.test',
  perfil: 'admin',
  escola_id: null,
  ativo: true,
}

function renderLogin(initialEntry: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/schools" element={<p>Página de escolas</p>} />
            <Route path="/" element={<p>Painel</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('E-mail'), email)
  await user.type(screen.getByLabelText('Senha'), password)
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
}

describe('LoginPage', () => {
  it('posts username and password as form fields to /auth/login', async () => {
    let body = new URLSearchParams()
    server.use(
      http.post(`${API}/auth/login`, async ({ request }) => {
        body = new URLSearchParams(await request.text())
        return HttpResponse.json({ access_token: 'tok', token_type: 'bearer' })
      }),
      http.get(`${API}/auth/me`, () => HttpResponse.json(usuario)),
    )

    renderLogin('/login')
    await fillAndSubmit('ana@educa.test', 'segredo')

    await waitFor(() => expect(body.get('username')).toBe('ana@educa.test'))
    expect(body.get('password')).toBe('segredo')
  })

  it('shows the API detail when credentials are wrong', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ detail: 'E-mail ou senha incorretos' }, { status: 401 }),
      ),
    )

    renderLogin('/login')
    await fillAndSubmit('ana@educa.test', 'errada')

    expect(await screen.findByText('E-mail ou senha incorretos')).toBeInTheDocument()
  })

  it('shows the rate limit message on 429', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ detail: 'rate' }, { status: 429 }),
      ),
    )

    renderLogin('/login')
    await fillAndSubmit('ana@educa.test', 'x')

    expect(
      await screen.findByText('Muitas tentativas. Tente novamente em 15 minutos'),
    ).toBeInTheDocument()
  })

  it('shows the session expired notice when expired=1', async () => {
    renderLogin('/login?expired=1')

    expect(await screen.findByText('Sua sessão expirou. Entre novamente')).toBeInTheDocument()
  })

  it('toggles the password visibility', async () => {
    renderLogin('/login')
    const user = userEvent.setup()
    const input = screen.getByLabelText('Senha')
    expect(input).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: 'Mostrar senha' }))
    expect(input).toHaveAttribute('type', 'text')

    await user.click(screen.getByRole('button', { name: 'Ocultar senha' }))
    expect(input).toHaveAttribute('type', 'password')
  })

  it('navigates to next after a successful login', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ access_token: 'tok', token_type: 'bearer' }),
      ),
      http.get(`${API}/auth/me`, () => HttpResponse.json(usuario)),
    )

    renderLogin('/login?next=/schools')
    await fillAndSubmit('ana@educa.test', 'segredo')

    expect(await screen.findByText('Página de escolas')).toBeInTheDocument()
  })

  it('ignores external next values and goes to the dashboard', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ access_token: 'tok', token_type: 'bearer' }),
      ),
      http.get(`${API}/auth/me`, () => HttpResponse.json(usuario)),
    )

    renderLogin('/login?next=//evil.test')
    await fillAndSubmit('ana@educa.test', 'segredo')

    expect(await screen.findByText('Painel')).toBeInTheDocument()
  })
})
