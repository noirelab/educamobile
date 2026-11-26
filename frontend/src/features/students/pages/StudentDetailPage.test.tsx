import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { StudentDetailPage } from './StudentDetailPage'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
  useMapEvents: () => null,
  useMap: () => ({ fitBounds: () => undefined }),
}))

const API = 'http://api.test'

const ROUTES = [{ path: '/students/:id', element: <StudentDetailPage /> }]

const ESTUDANTE = {
  id: 1,
  nome: 'Lucas Ferreira',
  data_nascimento: '2015-01-01',
  escola_id: 2,
  turno: 'tarde',
  parada_id: 5,
  observacoes_cuidado: 'Alergia a amendoim',
  tem_foto: false,
}

function mockApi() {
  server.use(
    http.get(`${API}/estudantes/1`, () => HttpResponse.json(ESTUDANTE)),
    http.get(`${API}/escolas/2`, () =>
      HttpResponse.json({
        id: 2,
        nome: 'EMEF Centro',
        codigo_inep: null,
        endereco: null,
        localizacao: { latitude: -25.4, longitude: -49.2 },
      }),
    ),
    http.get(`${API}/paradas`, () =>
      HttpResponse.json([{ id: 5, nome: 'Parada Centro', localizacao: { latitude: -25.43, longitude: -49.27 } }]),
    ),
  )
}

describe('StudentDetailPage', () => {
  it('shows school, shift, stop and care notes, and never a home location', async () => {
    mockApi()
    renderWithRoutes('/students/1', ROUTES, 'gestor')

    expect(await screen.findByRole('heading', { name: 'Lucas Ferreira' })).toBeInTheDocument()
    expect(await screen.findByText('EMEF Centro')).toBeInTheDocument()
    expect(screen.getByText('Tarde')).toBeInTheDocument()
    expect(await screen.findByText('Parada Centro')).toBeInTheDocument()
    expect(screen.getByText('Alergia a amendoim')).toBeInTheDocument()
    expect(screen.queryByText('Localização')).not.toBeInTheDocument()
    expect(screen.queryByText('Responsável')).not.toBeInTheDocument()
  })

  it('lets only the admin delete', async () => {
    mockApi()
    renderWithRoutes('/students/1', ROUTES, 'gestor')

    expect(await screen.findByRole('link', { name: 'Editar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
  })
})
