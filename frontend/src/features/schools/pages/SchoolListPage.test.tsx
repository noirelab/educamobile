import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { SchoolListPage } from './SchoolListPage'

const API = 'http://api.test'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Marker: () => <span data-testid="school-marker" />,
  useMapEvents: () => null,
}))

const ROUTES = [
  { path: '/schools', element: <SchoolListPage /> },
  { path: '/schools/new', element: <p>Nova escola</p> },
  { path: '/schools/:id', element: <p>Detalhe</p> },
]

const LOCATION = { latitude: -25.43, longitude: -49.27 }

const SCHOOLS = [
  { id: 1, nome: 'EMEF Centro', codigo_inep: '41000011', endereco: 'Rua A', polo_id: 1, localizacao: LOCATION },
  { id: 2, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: LOCATION },
]

const POLES = [{ id: 1, nome: 'Polo Centro', area: null }]

function mockLists(schools: unknown[] = SCHOOLS, onSchoolsRequest?: (url: URL) => void) {
  server.use(
    http.get(`${API}/polos`, () => HttpResponse.json(POLES)),
    http.get(`${API}/escolas`, ({ request }) => {
      onSchoolsRequest?.(new URL(request.url))
      return HttpResponse.json(schools)
    }),
  )
}

describe('SchoolListPage', () => {
  it('shows the pole name, or a dash when the school has no pole', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'coordenador')

    expect(await screen.findByText('EMEF Centro')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('Polo Centro')).toBeInTheDocument()
    expect(within(table).getAllByText('—')).toHaveLength(3)
  })

  it('filters by pole sending polo_id and resets the page', async () => {
    const requests: URL[] = []
    mockLists(SCHOOLS, (url) => requests.push(url))
    renderWithRoutes('/schools', ROUTES, 'coordenador')
    const user = userEvent.setup()

    await screen.findByText('EMEF Centro')
    expect(requests[0]?.searchParams.has('polo_id')).toBe(false)

    await user.selectOptions(screen.getByLabelText('Polo'), '1')

    await waitFor(() => expect(requests.at(-1)?.searchParams.get('polo_id')).toBe('1'))
  })

  it('switches to the map and renders one marker per school', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'coordenador')
    const user = userEvent.setup()

    await screen.findByText('EMEF Centro')
    await user.click(screen.getByRole('tab', { name: 'Mapa' }))

    expect(screen.getAllByTestId('school-marker')).toHaveLength(SCHOOLS.length)
  })

  it('shows Nova escola only for write roles', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'admin')

    expect(await screen.findByRole('link', { name: 'Nova escola' })).toBeInTheDocument()
  })

  it('hides Nova escola for diretor', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'diretor')

    expect(await screen.findByText('EMEF Centro')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nova escola' })).not.toBeInTheDocument()
  })

  it('shows the empty message when there are no schools', async () => {
    mockLists([])
    renderWithRoutes('/schools', ROUTES, 'admin')

    expect(await screen.findByText('Nenhuma escola cadastrada')).toBeInTheDocument()
  })
})
