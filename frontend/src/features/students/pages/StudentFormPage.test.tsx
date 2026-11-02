import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { StudentFormPage } from './StudentFormPage'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
  useMapEvents: () => null,
  useMap: () => ({ fitBounds: () => undefined }),
}))

const API = 'http://api.test'

const ROUTES = [
  { path: '/students/new', element: <StudentFormPage /> },
  { path: '/students/:id/edit', element: <StudentFormPage /> },
  { path: '/students/:id', element: <p>Detalhe do estudante</p> },
]

const TURMAS = [
  { id: 3, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 },
]

const PARADAS = [
  { id: 5, nome: 'Parada Centro', localizacao: { latitude: -25.43, longitude: -49.27 } },
]

const ESTUDANTE = {
  id: 1,
  nome: 'Lucas Ferreira',
  data_nascimento: '2015-01-01',
  nome_responsavel: 'Maria Ferreira',
  localizacao: null,
  parada_id: 5,
}

function mockLookups() {
  server.use(
    http.get(`${API}/turmas`, () => HttpResponse.json(TURMAS)),
    http.get(`${API}/paradas`, () => HttpResponse.json(PARADAS)),
    http.get(`${API}/estudantes/1`, () => HttpResponse.json(ESTUDANTE)),
  )
}

async function fillRequiredStudent(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Nome'), 'Lucas Ferreira')
  await user.type(screen.getByLabelText('Data de nascimento'), '2015-01-01')
}

describe('StudentFormPage', () => {
  it('blocks diretor create without matrícula and hides the parada field', async () => {
    mockLookups()
    let posted = false
    server.use(
      http.post(`${API}/estudantes`, () => {
        posted = true
        return HttpResponse.json(ESTUDANTE, { status: 201 })
      }),
    )
    renderWithRoutes('/students/new', ROUTES, 'diretor', 1)
    const user = userEvent.setup()

    await screen.findByRole('option', { name: '6A' })
    await fillRequiredStudent(user)
    await user.clear(screen.getByLabelText('Data de início'))
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Informe a turma e a data de início')).toBeInTheDocument()
    expect(screen.queryByLabelText('Parada')).not.toBeInTheDocument()
    expect(posted).toBe(false)
  })

  it('shows parada and keeps matrícula optional for admin create', async () => {
    mockLookups()
    let body: Record<string, unknown> | undefined
    server.use(
      http.post(`${API}/estudantes`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(ESTUDANTE, { status: 201 })
      }),
    )
    renderWithRoutes('/students/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'Parada Centro' })
    expect(screen.getByLabelText('Parada')).toBeInTheDocument()
    expect(screen.getByText('Opcional para administrador')).toBeInTheDocument()
    await fillRequiredStudent(user)
    await user.selectOptions(screen.getByLabelText('Parada'), '5')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toBeDefined())
    expect(body).not.toHaveProperty('matricula')
    expect(body).toMatchObject({ nome: 'Lucas Ferreira', parada_id: 5 })
  })

  it('edit sends PUT without matrícula and without parada for diretor', async () => {
    mockLookups()
    let body: Record<string, unknown> | undefined
    server.use(
      http.put(`${API}/estudantes/1`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(ESTUDANTE)
      }),
    )
    renderWithRoutes('/students/1/edit', ROUTES, 'diretor', 1)
    const user = userEvent.setup()

    expect(await screen.findByDisplayValue('Lucas Ferreira')).toBeInTheDocument()
    expect(screen.queryByLabelText('Turma')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Parada')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toBeDefined())
    expect(body).not.toHaveProperty('matricula')
    expect(body).not.toHaveProperty('parada_id')
  })
})
