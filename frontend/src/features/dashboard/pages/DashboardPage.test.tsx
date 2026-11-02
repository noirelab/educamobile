import { cloneElement } from 'react'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { DashboardPage } from './DashboardPage'

vi.mock('../components/HeatLayer', () => ({ HeatLayer: () => null }))

const API = 'http://api.test'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  CircleMarker: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Polygon: () => null,
  Polyline: () => null,
  useMap: () => ({}),
}))

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) => (
      <div>{cloneElement(children, { width: 600, height: 280 })}</div>
    ),
  }
})

const ROUTES = [{ path: '/', element: <DashboardPage /> }, { path: '/schools/:id', element: <p>Detalhe</p> }, { path: '/routes', element: <p>Rotas</p> }]

const SCHOOLS = [
  { id: 1, nome: 'EMEF A', codigo_inep: null, endereco: null, polo_id: null, localizacao: { latitude: -25.4, longitude: -49.2 } },
  { id: 2, nome: 'EMEF B', codigo_inep: null, endereco: null, polo_id: null, localizacao: { latitude: -25.5, longitude: -49.3 } },
  { id: 3, nome: 'EMEF C', codigo_inep: null, endereco: null, polo_id: null, localizacao: { latitude: -25.6, longitude: -49.4 } },
]

const ESCOLA_ROWS = [
  { grupo_id: 1, grupo_nome: 'EMEF A', total_registros: 10, presencas: 6, faltas: 4, taxa_infrequencia: 0.4 },
  { grupo_id: 2, grupo_nome: 'EMEF B', total_registros: 100, presencas: 88, faltas: 12, taxa_infrequencia: 0.12 },
  { grupo_id: 3, grupo_nome: 'EMEF C', total_registros: 50, presencas: 50, faltas: 0, taxa_infrequencia: 0 },
]

const POLO_ROWS = [{ grupo_id: 1, grupo_nome: 'Polo Centro', total_registros: 160, presencas: 144, faltas: 16, taxa_infrequencia: 0.1 }]

function aggregateHandler(requests: URL[] = []) {
  return http.get(`${API}/frequencias/agregada`, ({ request }) => {
    const url = new URL(request.url)
    requests.push(url)
    if (url.searchParams.get('agrupar') === 'escola') return HttpResponse.json(ESCOLA_ROWS)
    if (url.searchParams.get('agrupar') === 'polo') return HttpResponse.json(POLO_ROWS)
    return HttpResponse.json(ESCOLA_ROWS)
  })
}

describe('DashboardPage', () => {
  it('coordenador sees logistics cards and makes no aggregate request', async () => {
    const aggregateCalls = vi.fn()
    server.use(
      http.get(`${API}/frequencias/agregada`, () => {
        aggregateCalls()
        return HttpResponse.json([])
      }),
      http.get(`${API}/rotas`, () =>
        HttpResponse.json([
          { id: 1, nome: 'R1', distancia_m: 1500, paradas: [], trajeto: null },
          { id: 2, nome: 'R2', distancia_m: null, paradas: [], trajeto: null },
        ]),
      ),
      http.get(`${API}/paradas`, () =>
        HttpResponse.json([{ id: 1, nome: 'P1', localizacao: { latitude: -25.4, longitude: -49.2 } }]),
      ),
    )
    renderWithRoutes('/', ROUTES, 'coordenador')

    expect(await screen.findByText('Transporte escolar')).toBeInTheDocument()
    expect(await screen.findByText('1.500 m')).toBeInTheDocument()
    expect(screen.getByText('Ver rotas')).toBeInTheDocument()
    expect(aggregateCalls).not.toHaveBeenCalled()
  })

  it('diretor sees no map', async () => {
    server.use(aggregateHandler())
    renderWithRoutes('/', ROUTES, 'diretor')

    expect(await screen.findByText('Infrequência da escola')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Infrequência')).toBeInTheDocument())
    expect(screen.queryByTestId('map')).not.toBeInTheDocument()
  })

  it('admin ranks schools by infrequency with links to the detail page', async () => {
    server.use(
      aggregateHandler(),
      http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)),
      http.get(`${API}/polos`, () => HttpResponse.json([])),
    )
    renderWithRoutes('/', ROUTES, 'admin')

    const ranking = await screen.findByRole('list', { name: 'Escolas com mais faltas' })
    const items = within(ranking).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining('40,0%'),
      expect.stringContaining('12,0%'),
      expect.stringContaining('0,0%'),
    ])
    expect(within(ranking).getByRole('link', { name: 'EMEF A' })).toHaveAttribute('href', '/schools/1')
  })

  it('admin chart tab requests the selected grouping', async () => {
    const requests: URL[] = []
    server.use(
      aggregateHandler(requests),
      http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)),
      http.get(`${API}/polos`, () => HttpResponse.json([])),
    )
    renderWithRoutes('/', ROUTES, 'admin')
    await screen.findByRole('list', { name: 'Escolas com mais faltas' })

    await userEvent.click(screen.getByRole('tab', { name: 'Turma' }))

    await waitFor(() =>
      expect(requests.some((url) => url.searchParams.get('agrupar') === 'turma')).toBe(true),
    )
  })

  it('admin chart renders one bar per row', async () => {
    server.use(
      aggregateHandler(),
      http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)),
      http.get(`${API}/polos`, () => HttpResponse.json([])),
    )
    const { container } = renderWithRoutes('/', ROUTES, 'admin')
    await screen.findByRole('list', { name: 'Escolas com mais faltas' })

    await waitFor(() => expect(container.querySelectorAll('.recharts-bar-rectangle path').length).toBe(POLO_ROWS.length))
  })

  it('shows the empty copy when the period has no records', async () => {
    server.use(
      http.get(`${API}/frequencias/agregada`, () => HttpResponse.json([])),
      http.get(`${API}/escolas`, () => HttpResponse.json([])),
      http.get(`${API}/polos`, () => HttpResponse.json([])),
    )
    renderWithRoutes('/?data_inicio=2026-10-19&data_fim=2026-10-23', ROUTES, 'admin')

    expect(
      await screen.findByText('Nenhum registro de frequência entre 19/10/2026 e 23/10/2026'),
    ).toBeInTheDocument()
  })
})
