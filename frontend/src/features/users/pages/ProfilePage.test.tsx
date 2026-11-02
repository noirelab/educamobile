import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { ProfilePage } from './ProfilePage'

const API = 'http://api.test'

const ROUTES = [{ path: '/profile', element: <ProfilePage /> }]

describe('ProfilePage', () => {
  it('shows the user data from GET /auth/me without edit controls', async () => {
    renderWithRoutes('/profile', ROUTES, 'coordenador')
    expect(await screen.findByRole('heading', { level: 1, name: 'Ana' })).toBeInTheDocument()
    expect(screen.getByText('ana@educa.test')).toBeInTheDocument()
    expect(screen.getAllByText('Coordenador de logística').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.getByText('A troca de senha ainda não está disponível')).toBeInTheDocument()
  })

  it('shows the school name for diretor', async () => {
    server.use(
      http.get(`${API}/escolas/7`, () =>
        HttpResponse.json({ id: 7, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: null }),
      ),
    )
    renderWithRoutes('/profile', ROUTES, 'diretor', 7)
    expect(await screen.findByText('EMEF Sul')).toBeInTheDocument()
    expect(screen.getAllByText('Diretor').length).toBeGreaterThan(0)
  })

  it('omits the school row for admin', async () => {
    renderWithRoutes('/profile', ROUTES, 'admin')
    expect(await screen.findByRole('heading', { level: 1, name: 'Ana' })).toBeInTheDocument()
    expect(screen.getAllByText('Administrador').length).toBeGreaterThan(0)
    expect(screen.queryByText('Escola')).not.toBeInTheDocument()
  })
})
