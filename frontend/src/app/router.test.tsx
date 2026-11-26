import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { setToken } from '@/shared/auth/session'
import { Providers } from './providers'
import { routes } from './router'

const API = 'http://api.test'

type Perfil = 'admin' | 'gestor' | 'motorista'

function renderAt(path: string, perfil: Perfil = 'gestor') {
  setToken('tok')
  server.use(
    http.get(`${API}/auth/me`, () =>
      HttpResponse.json({
        id: 1,
        nome: 'Ana',
        email: 'ana@educa.test',
        perfil,
        ativo: true,
      }),
    ),
  )
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <Providers>
      <RouterProvider router={router} />
    </Providers>,
  )
}

describe('app router', () => {
  it('shows user name, role label and Sair in the topbar', async () => {
    renderAt('/', 'admin')

    expect(await screen.findByText('Ana')).toBeInTheDocument()
    expect(screen.getByText('Administrador')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sair' })).toBeInTheDocument()
  })

  it('shows the gestor role label', async () => {
    renderAt('/')

    expect(await screen.findByText('Gestor de transporte')).toBeInTheDocument()
  })

  it('shows the page breadcrumb and the sidebar brand caption', async () => {
    renderAt('/', 'admin')

    expect(await screen.findByText('Transporte escolar seguro')).toBeInTheDocument()
    const crumbs = screen.getByRole('navigation', { name: 'Trilha de navegação' })
    expect(within(crumbs).getByText('Painel')).toBeInTheDocument()
    expect(screen.getByText('Secretaria de Educação')).toBeInTheDocument()
  })

  it('renders the 403 copy when the role has no access', async () => {
    renderAt('/students', 'motorista')

    expect(
      await screen.findByText('Você não tem permissão para acessar esta página'),
    ).toBeInTheDocument()
  })

  it('renders the 404 copy for unknown paths', async () => {
    renderAt('/rota-inexistente')

    expect(await screen.findByText('Página não encontrada')).toBeInTheDocument()
  })
})
