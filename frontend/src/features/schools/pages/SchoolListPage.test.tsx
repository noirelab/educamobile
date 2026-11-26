import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
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
  { id: 1, nome: 'EMEF Centro', codigo_inep: '41000011', endereco: 'Rua A', localizacao: LOCATION },
  { id: 2, nome: 'EMEF Sul', codigo_inep: null, endereco: null, localizacao: LOCATION },
]

function mockLists(schools: unknown[] = SCHOOLS) {
  server.use(
    http.get(`${API}/escolas`, () => HttpResponse.json(schools)),
  )
}

describe('SchoolListPage', () => {
  it('lists the schools with INEP and address, or a dash when missing', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'gestor')

    expect(await screen.findByText('EMEF Centro')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('41000011')).toBeInTheDocument()
    expect(within(table).getAllByText('—')).toHaveLength(2)
  })

  it('switches to the map and renders one marker per school', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'gestor')
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

  it('hides Nova escola for gestor', async () => {
    mockLists()
    renderWithRoutes('/schools', ROUTES, 'gestor')

    expect(await screen.findByText('EMEF Centro')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nova escola' })).not.toBeInTheDocument()
  })

  it('shows the empty message when there are no schools', async () => {
    mockLists([])
    renderWithRoutes('/schools', ROUTES, 'admin')

    expect(await screen.findByText('Nenhuma escola cadastrada')).toBeInTheDocument()
  })
})
