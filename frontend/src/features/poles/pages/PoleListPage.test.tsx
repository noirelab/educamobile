import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { PoleListPage } from './PoleListPage'

const API = 'http://api.test'

const AREA = {
  type: 'MultiPolygon' as const,
  coordinates: [
    [
      [
        [-49.27, -25.43],
        [-49.26, -25.43],
        [-49.26, -25.42],
        [-49.27, -25.43],
      ],
    ],
  ],
}

const ROUTES = [
  { path: '/poles', element: <PoleListPage /> },
  { path: '/poles/new', element: <p>Novo polo</p> },
  { path: '/poles/:id', element: <p>Detalhe</p> },
]

function mockPoles(rows: unknown[]) {
  server.use(http.get(`${API}/polos`, () => HttpResponse.json(rows)))
}

describe('PoleListPage', () => {
  it('shows the Área column as Sim or Não', async () => {
    mockPoles([
      { id: 1, nome: 'Polo Centro', area: AREA },
      { id: 2, nome: 'Polo Sul', area: null },
    ])
    renderWithRoutes('/poles', ROUTES, 'coordenador')

    expect(await screen.findByText('Polo Centro')).toBeInTheDocument()
    expect(screen.getByText('Sim')).toBeInTheDocument()
    expect(screen.getByText('Não')).toBeInTheDocument()
  })

  it('shows Novo polo for admin', async () => {
    mockPoles([{ id: 1, nome: 'Polo Centro', area: null }])
    renderWithRoutes('/poles', ROUTES, 'admin')

    expect(await screen.findByRole('link', { name: 'Novo polo' })).toBeInTheDocument()
  })

  it('hides Novo polo for diretor', async () => {
    mockPoles([{ id: 1, nome: 'Polo Centro', area: null }])
    renderWithRoutes('/poles', ROUTES, 'diretor')

    expect(await screen.findByText('Polo Centro')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Novo polo' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
  })

  it('shows the empty message when there are no poles', async () => {
    mockPoles([])
    renderWithRoutes('/poles', ROUTES, 'admin')

    expect(await screen.findByText('Nenhum polo cadastrado')).toBeInTheDocument()
  })
})
