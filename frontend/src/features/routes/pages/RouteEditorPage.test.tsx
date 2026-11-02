import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { RouteEditorPage } from './RouteEditorPage'

const API = 'http://api.test'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Polyline: () => null,
  Popup: () => null,
  Marker: ({
    title,
    eventHandlers,
  }: {
    title?: string
    eventHandlers?: { click?: () => void }
  }) =>
    eventHandlers?.click ? (
      <button type="button" aria-label={`Marcador ${title}`} onClick={() => eventHandlers.click?.()} />
    ) : null,
  useMapEvents: () => null,
  useMap: () => ({ fitBounds: () => undefined }),
}))

const STOPS = [
  { id: 1, nome: 'Parada Centro', localizacao: { latitude: -25.4, longitude: -49.2 } },
  { id: 2, nome: 'Parada Norte', localizacao: { latitude: -25.3, longitude: -49.1 } },
  { id: 3, nome: 'Parada Sul', localizacao: { latitude: -25.5, longitude: -49.3 } },
]

const ROUTE = {
  id: 4,
  nome: 'Rota Norte',
  distancia_m: 4493,
  paradas: [STOPS[0], STOPS[1]],
  trajeto: {
    type: 'LineString',
    coordinates: [
      [-49.2, -25.4],
      [-49.1, -25.3],
    ],
  },
}

const EMPTY_ROUTE: RouteFixture = { id: 5, nome: 'Rota Vazia', distancia_m: null, paradas: [], trajeto: null }

const ROUTES = [{ path: '/routes/:id', element: <RouteEditorPage /> }, { path: '/routes', element: <p>Lista de rotas</p> }]

type RouteFixture = { id: number; nome: string; distancia_m: number | null; paradas: typeof STOPS; trajeto: unknown }

function mockBase(route: RouteFixture = ROUTE) {
  server.use(
    http.get(`${API}/rotas/${route.id}`, () => HttpResponse.json(route)),
    http.get(`${API}/paradas`, () => HttpResponse.json(STOPS)),
  )
}

describe('RouteEditorPage', () => {
  it('saves the current order and shows the distance before and after', async () => {
    mockBase()
    let body: unknown
    server.use(
      http.put(`${API}/rotas/4/paradas`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...ROUTE, distancia_m: 3980, paradas: [STOPS[0], STOPS[1], STOPS[2]] })
      }),
    )
    renderWithRoutes('/routes/4', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Marcador Parada Sul' }))
    await user.click(screen.getByRole('button', { name: 'Salvar sequência' }))

    await waitFor(() => expect(body).toEqual({ parada_ids: [1, 2, 3] }))
    expect(await screen.findByText('4.493 m → 3.980 m')).toBeInTheDocument()
  })

  it('shows a 409 on the name field when renaming to a taken name', async () => {
    mockBase()
    server.use(
      http.patch(`${API}/rotas/4`, () =>
        HttpResponse.json({ detail: 'Nome já existe' }, { status: 409 }),
      ),
    )
    renderWithRoutes('/routes/4', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Renomear' }))
    const dialog = await screen.findByRole('dialog', { name: 'Renomear rota' })
    await user.clear(within(dialog).getByLabelText('Nome'))
    await user.type(within(dialog).getByLabelText('Nome'), 'Rota Sul')
    await user.click(within(dialog).getByRole('button', { name: 'Salvar' }))

    expect(await within(dialog).findByText('Conflito com outra rota')).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Nome')).toHaveAttribute('aria-invalid', 'true')
  })

  it('always shows the straight line disclaimer', async () => {
    mockBase()
    renderWithRoutes('/routes/4', ROUTES, 'admin')

    expect(await screen.findByText('Trajeto em linha reta entre paradas')).toBeInTheDocument()
  })

  it('shows the hint when the route has no stops', async () => {
    mockBase(EMPTY_ROUTE)
    renderWithRoutes('/routes/5', ROUTES, 'admin')

    expect(await screen.findByText('Adicione paradas clicando no mapa')).toBeInTheDocument()
  })

  it('is read-only for diretor', async () => {
    mockBase()
    renderWithRoutes('/routes/4', ROUTES, 'diretor')

    expect(await screen.findByText('Rota Norte', { selector: 'h1' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Renomear' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Salvar sequência' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remover Parada Centro' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Marcador Parada Sul' })).not.toBeInTheDocument()
  })

  it('adds a stop on map click without changing the saved order until saved', async () => {
    mockBase()
    renderWithRoutes('/routes/4', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Marcador Parada Sul' }))

    expect(await screen.findByRole('button', { name: 'Remover Parada Sul' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar sequência' })).toBeEnabled()
  })
})
