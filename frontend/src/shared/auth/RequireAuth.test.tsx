import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { api } from '@/shared/api/client'
import { getToken, setToken } from '@/shared/auth/session'
import { AuthProvider } from './AuthProvider'
import { RequireAuth } from './RequireAuth'
import { RequireAccess } from './RequireAccess'

const API = 'http://api.test'

afterEach(cleanup)

const usuario = {
  id: 1,
  nome: 'Ana',
  email: 'ana@educa.test',
  perfil: 'coordenador',
  escola_id: null,
  ativo: true,
}

function LocationProbe() {
  const location = useLocation()
  return <p>{`${location.pathname}${location.search}`}</p>
}

function StudentEdit() {
  const query = useQuery({
    queryKey: ['estudante', 5],
    queryFn: () => api('/estudantes/5'),
  })
  return <p>{query.isSuccess ? 'Editando' : 'Carregando'}</p>
}

function renderApp(initialEntry: string, element: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LocationProbe />} />
            <Route path="/students/:id/edit" element={<RequireAuth>{element}</RequireAuth>} />
            <Route path="/" element={<p>Raiz</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RequireAuth', () => {
  it('redirects to login with next when there is no session', async () => {
    renderApp('/students/5/edit', <p>Protegido</p>)

    expect(await screen.findByText('/login?next=%2Fstudents%2F5%2Fedit')).toBeInTheDocument()
    expect(screen.queryByText('Protegido')).not.toBeInTheDocument()
  })

  it('on a 401 from a query clears the token and redirects with expired and next', async () => {
    setToken('expirado')
    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json(usuario)),
      http.get(`${API}/estudantes/5`, () =>
        HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
      ),
    )

    renderApp('/students/5/edit', <StudentEdit />)

    expect(
      await screen.findByText('/login?expired=1&next=%2Fstudents%2F5%2Fedit'),
    ).toBeInTheDocument()
    await waitFor(() => expect(getToken()).toBeNull())
  })
})

describe('RequireAccess', () => {
  it('renders the forbidden page when the role has no access', async () => {
    setToken('tok')
    server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(usuario)))

    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/usuarios']}>
          <AuthProvider>
            <RequireAccess resource="users" level="read">
              <p>Lista de usuários</p>
            </RequireAccess>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(
      await screen.findByText('Você não tem permissão para acessar esta página'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Lista de usuários')).not.toBeInTheDocument()
  })
})
