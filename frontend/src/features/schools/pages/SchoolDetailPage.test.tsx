import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { SchoolDetailPage } from './SchoolDetailPage'

const API = 'http://api.test'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
  useMapEvents: () => null,
}))

const ROUTES = [
  { path: '/schools/:id', element: <SchoolDetailPage /> },
  { path: '/schools', element: <p>Lista de escolas</p> },
  { path: '/schools/:id/edit', element: <p>Editar</p> },
]

const SCHOOL = {
  id: 1,
  nome: 'EMEF Centro',
  codigo_inep: '41000011',
  endereco: 'Rua A',
  localizacao: { latitude: -25.43, longitude: -49.27 },
}

describe('SchoolDetailPage', () => {
  it('shows the school data without the old pole, class and attendance blocks', async () => {
    server.use(http.get(`${API}/escolas/1`, () => HttpResponse.json(SCHOOL)))
    renderWithRoutes('/schools/1', ROUTES, 'admin')

    expect(await screen.findByRole('heading', { name: 'EMEF Centro' })).toBeInTheDocument()
    expect(screen.getByText('Rua A')).toBeInTheDocument()
    expect(screen.queryByText('Polo')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Turmas' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Professores' })).not.toBeInTheDocument()
  })

  it('offers edit and delete to the admin', async () => {
    server.use(http.get(`${API}/escolas/1`, () => HttpResponse.json(SCHOOL)))
    renderWithRoutes('/schools/1', ROUTES, 'admin')

    expect(await screen.findByRole('link', { name: 'Editar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Excluir' })).toBeInTheDocument()
  })

  it('is read-only for the gestor', async () => {
    server.use(http.get(`${API}/escolas/1`, () => HttpResponse.json(SCHOOL)))
    renderWithRoutes('/schools/1', ROUTES, 'gestor')

    expect(await screen.findByRole('heading', { name: 'EMEF Centro' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
  })
})
