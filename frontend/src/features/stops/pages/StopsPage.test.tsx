import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { StopsPage } from './StopsPage'

const API = 'http://api.test'

const mapEvents = vi.hoisted(() => ({ click: undefined as undefined | ((event: unknown) => void) }))

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Circle: () => null,
  Marker: ({
    title,
    draggable,
    eventHandlers,
  }: {
    title?: string
    draggable?: boolean
    eventHandlers?: { dragend?: (event: unknown) => void }
  }) => (
    <div>
      <span data-testid={`marker-${title}`} />
      {draggable && (
        <button
          type="button"
          aria-label={`Arrastar ${title}`}
          onClick={() =>
            eventHandlers?.dragend?.({ target: { getLatLng: () => ({ lat: -25.2, lng: -49.2 }) } })
          }
        />
      )}
    </div>
  ),
  useMapEvents: (handlers: { click?: (event: unknown) => void }) => {
    mapEvents.click = handlers.click
    return null
  },
  useMap: () => ({ fitBounds: () => undefined }),
}))

const STOPS = [
  { id: 1, nome: 'Parada Centro', localizacao: { latitude: -25.4, longitude: -49.2 } },
  { id: 2, nome: 'Parada Norte', localizacao: { latitude: -25.3, longitude: -49.1 } },
]

const ROUTES = [
  { path: '/stops', element: <StopsPage /> },
  { path: '/stops/:id', element: <p>Detalhe da parada</p> },
]

function mockStops() {
  server.use(http.get(`${API}/paradas`, () => HttpResponse.json(STOPS)))
}

describe('StopsPage', () => {
  it('opens the create dialog from a map click and posts the new stop', async () => {
    mockStops()
    let body: unknown
    server.use(
      http.post(`${API}/paradas`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 3, ...(body as object) }, { status: 201 })
      }),
    )
    renderWithRoutes('/stops', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Nova parada' }))
    act(() => mapEvents.click?.({ latlng: { lat: -25.3, lng: -49.2 } }))
    const dialog = await screen.findByRole('dialog', { name: 'Nova parada' })
    expect(within(dialog).getByText('-25.3')).toBeInTheDocument()
    expect(within(dialog).getByText('-49.2')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Nome'), 'Parada Sul')
    await user.click(within(dialog).getByRole('button', { name: 'Salvar' }))

    await waitFor(() =>
      expect(body).toEqual({ nome: 'Parada Sul', localizacao: { latitude: -25.3, longitude: -49.2 } }),
    )
  })

  it('sends only localizacao when a marker is dragged', async () => {
    mockStops()
    let body: unknown
    server.use(
      http.patch(`${API}/paradas/1`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...STOPS[0], ...(body as object) })
      }),
    )
    renderWithRoutes('/stops', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Arrastar Parada Centro' }))

    await waitFor(() => expect(body).toEqual({ localizacao: { latitude: -25.2, longitude: -49.2 } }))
  })

  it('hides create and drag actions for diretor', async () => {
    mockStops()
    renderWithRoutes('/stops', ROUTES, 'diretor')

    expect(await screen.findByTestId('marker-Parada Centro')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Nova parada' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Arrastar Parada Centro' })).not.toBeInTheDocument()
  })
})
