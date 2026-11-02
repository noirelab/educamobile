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
  polo_id: 1,
  localizacao: { latitude: -25.43, longitude: -49.27 },
}

const CLASSES = [{ id: 5, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 }]

function mockDetail(attendance: unknown[] = [], attendanceCalls?: { count: number }) {
  server.use(
    http.get(`${API}/escolas/1`, () => HttpResponse.json(SCHOOL)),
    http.get(`${API}/polos`, () => HttpResponse.json([{ id: 1, nome: 'Polo Centro', area: null }])),
    http.get(`${API}/turmas`, () => HttpResponse.json(CLASSES)),
    http.get(`${API}/professores`, () =>
      HttpResponse.json([{ id: 2, nome: 'Carla', email: 'carla@educa.test', escola_id: 1 }]),
    ),
    http.get(`${API}/frequencias/agregada`, () => {
      if (attendanceCalls) attendanceCalls.count += 1
      return HttpResponse.json(attendance)
    }),
  )
}

const ATTENDANCE = [
  { grupo_id: 5, grupo_nome: '6A', total_registros: 10, presencas: 8, faltas: 2, taxa_infrequencia: 0.2 },
]

describe('SchoolDetailPage', () => {
  it('shows the Infrequência por turma block for diretor', async () => {
    mockDetail(ATTENDANCE)
    renderWithRoutes('/schools/1', ROUTES, 'diretor')

    expect(await screen.findByRole('heading', { name: 'Infrequência por turma' })).toBeInTheDocument()
    expect(await screen.findByText('20,0%')).toBeInTheDocument()
  })

  it('does not show or request the attendance block for admin', async () => {
    const calls = { count: 0 }
    mockDetail(ATTENDANCE, calls)
    renderWithRoutes('/schools/1', ROUTES, 'admin')

    expect(await screen.findByRole('heading', { name: 'Turmas' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Infrequência por turma' })).not.toBeInTheDocument()
    expect(calls.count).toBe(0)
  })

  it('shows the empty attendance message when there are no records', async () => {
    mockDetail([])
    renderWithRoutes('/schools/1', ROUTES, 'diretor')

    expect(await screen.findByText('Nenhum registro de frequência no período')).toBeInTheDocument()
  })

  it('hides the Professores section for coordenador', async () => {
    mockDetail()
    renderWithRoutes('/schools/1', ROUTES, 'coordenador')

    expect(await screen.findByRole('heading', { name: 'Turmas' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Professores' })).not.toBeInTheDocument()
  })

  it('shows the Professores section for diretor', async () => {
    mockDetail()
    renderWithRoutes('/schools/1', ROUTES, 'diretor')

    expect(await screen.findByText('Carla')).toBeInTheDocument()
  })
})
