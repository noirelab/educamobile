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
  nome_responsavel: 'Maria Ferreira',
  localizacao: { latitude: -25.44, longitude: -49.28 },
  parada_id: 5,
}

describe('StudentDetailPage', () => {
  it('coordenador sees no enrollment history and makes no /matriculas request', async () => {
    let enrollmentRequests = 0
    server.use(
      http.get(`${API}/estudantes/1`, () => HttpResponse.json(ESTUDANTE)),
      http.get(`${API}/paradas`, () =>
        HttpResponse.json([{ id: 5, nome: 'Parada Centro', localizacao: { latitude: -25.43, longitude: -49.27 } }]),
      ),
      http.get(`${API}/matriculas/historico/:id`, () => {
        enrollmentRequests += 1
        return HttpResponse.json([])
      }),
      http.get(`${API}/matriculas`, () => {
        enrollmentRequests += 1
        return HttpResponse.json([])
      }),
    )
    renderWithRoutes('/students/1', ROUTES, 'coordenador')

    expect(await screen.findByRole('heading', { name: 'Lucas Ferreira' })).toBeInTheDocument()
    expect(await screen.findByText('Disponível em breve')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Matrículas' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
    expect(enrollmentRequests).toBe(0)
  })
})
