import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { SchoolFormPage } from './SchoolFormPage'

const API = 'http://api.test'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
  useMapEvents: () => null,
}))

const ROUTES = [
  { path: '/schools/new', element: <SchoolFormPage /> },
  { path: '/schools/:id/edit', element: <SchoolFormPage /> },
  { path: '/schools/:id', element: <p>Detalhe da escola</p> },
]

const POLES = [{ id: 1, nome: 'Polo Centro', area: null }]

function mockPoles() {
  server.use(http.get(`${API}/polos`, () => HttpResponse.json(POLES)))
}

async function fillLocation(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Latitude'), '-25.43')
  await user.type(screen.getByLabelText('Longitude'), '-49.27')
}

describe('SchoolFormPage', () => {
  it('posts null for empty optional fields', async () => {
    mockPoles()
    let body: unknown
    server.use(
      http.post(`${API}/escolas`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9, nome: 'EMEF Centro' }, { status: 201 })
      }),
    )
    renderWithRoutes('/schools/new', ROUTES)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Nome'), 'EMEF Centro')
    await fillLocation(user)
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() =>
      expect(body).toEqual({
        nome: 'EMEF Centro',
        codigo_inep: null,
        endereco: null,
        polo_id: null,
        localizacao: { latitude: -25.43, longitude: -49.27 },
      }),
    )
  })

  it('blocks submit when codigo_inep does not have 8 digits', async () => {
    mockPoles()
    let called = false
    server.use(
      http.post(`${API}/escolas`, () => {
        called = true
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    renderWithRoutes('/schools/new', ROUTES)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Nome'), 'EMEF Centro')
    await user.type(screen.getByLabelText('Código INEP'), '4100001')
    await fillLocation(user)
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('O código INEP tem 8 dígitos')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('requires the location on the map', async () => {
    mockPoles()
    renderWithRoutes('/schools/new', ROUTES)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Nome'), 'EMEF Centro')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Marque a localização no mapa')).toBeInTheDocument()
  })

  it('shows the INEP conflict on the codigo_inep field', async () => {
    mockPoles()
    server.use(
      http.post(`${API}/escolas`, () =>
        HttpResponse.json(
          { detail: 'Código INEP já cadastrado ou polo inexistente' },
          { status: 409 },
        ),
      ),
    )
    renderWithRoutes('/schools/new', ROUTES)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Nome'), 'EMEF Centro')
    await user.type(screen.getByLabelText('Código INEP'), '41000011')
    await fillLocation(user)
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(
      await screen.findByText('Código INEP já cadastrado ou polo inexistente'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Código INEP')).toHaveAttribute('aria-invalid', 'true')
  })

  it('loads the school and sends PUT on edit', async () => {
    mockPoles()
    let body: unknown
    server.use(
      http.get(`${API}/escolas/3`, () =>
        HttpResponse.json({
          id: 3,
          nome: 'EMEF Sul',
          codigo_inep: '41000011',
          endereco: 'Rua A, 10',
          polo_id: 1,
          localizacao: { latitude: -25.5, longitude: -49.3 },
        }),
      ),
      http.put(`${API}/escolas/3`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 3, nome: 'EMEF Sul II' })
      }),
    )
    renderWithRoutes('/schools/3/edit', ROUTES)
    const user = userEvent.setup()

    expect(await screen.findByRole('heading', { name: 'Editar escola' })).toBeInTheDocument()
    const nome = screen.getByLabelText('Nome')
    await user.clear(nome)
    await user.type(nome, 'EMEF Sul II')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() =>
      expect(body).toEqual({
        nome: 'EMEF Sul II',
        codigo_inep: '41000011',
        endereco: 'Rua A, 10',
        polo_id: 1,
        localizacao: { latitude: -25.5, longitude: -49.3 },
      }),
    )
  })
})
