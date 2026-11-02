import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, Outlet, RouterProvider, type RouteObject } from 'react-router-dom'
import { AuthProvider } from '@/shared/auth/AuthProvider'
import type { Role } from '@/shared/auth/permissions'
import { setToken } from '@/shared/auth/session'
import { server } from './server'

const API = 'http://api.test'

export function renderWithRoutes(
  path: string,
  routes: RouteObject[],
  perfil: Role = 'admin',
  escolaId: number | null = null,
) {
  setToken('tok')
  server.use(
    http.get(`${API}/auth/me`, () =>
      HttpResponse.json({
        id: 1,
        nome: 'Ana',
        email: 'ana@educa.test',
        perfil,
        escola_id: escolaId,
        ativo: true,
      }),
    ),
  )
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(
    [{ element: <AuthProvider><Outlet /></AuthProvider>, children: routes }],
    { initialEntries: [path] },
  )
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}
