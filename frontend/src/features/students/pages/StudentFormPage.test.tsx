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

const ESCOLAS = [
  { id: 2, nome: 'EMEF Centro', codigo_inep: null, endereco: null, localizacao: { latitude: -25.4, longitude: -49.2 } },
]

const PARADAS = [
  { id: 5, nome: 'Parada Centro', localizacao: { latitude: -25.43, longitude: -49.27 } },
]

const ESTUDANTE = {
  id: 1,
  nome: 'Lucas Ferreira',
  data_nascimento: '2015-01-01',
  escola_id: 2,
  turno: 'tarde',
  parada_id: 5,
  observacoes_cuidado: null,
  tem_foto: false,
}

function mockLookups() {
  server.use(
    http.get(`${API}/escolas`, () => HttpResponse.json(ESCOLAS)),
    http.get(`${API}/paradas`, () => HttpResponse.json(PARADAS)),
    http.get(`${API}/estudantes/1`, () => HttpResponse.json(ESTUDANTE)),
  )
}

async function fillRequiredStudent(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Nome'), 'Lucas Ferreira')
  await user.type(screen.getByLabelText('Data de nascimento'), '2015-01-01')
}

describe('StudentFormPage', () => {
  it('blocks the save without a school and does not post', async () => {
    mockLookups()
    let posted = false
    server.use(
      http.post(`${API}/estudantes`, () => {
        posted = true
        return HttpResponse.json(ESTUDANTE, { status: 201 })
      }),
    )
    renderWithRoutes('/students/new', ROUTES, 'gestor')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Centro' })
    await fillRequiredStudent(user)
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Informe a escola')).toBeInTheDocument()
    expect(posted).toBe(false)
  })

  it('asks for no home address, location or guardian name', async () => {
    mockLookups()
    renderWithRoutes('/students/new', ROUTES, 'gestor')

    await screen.findByRole('option', { name: 'EMEF Centro' })
    expect(screen.queryByLabelText('Responsável')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Latitude')).not.toBeInTheDocument()
    expect(screen.queryByText(/Localização/)).not.toBeInTheDocument()
  })

  it('posts school, shift, stop and care notes', async () => {
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
    await fillRequiredStudent(user)
    await user.selectOptions(screen.getByLabelText('Escola'), '2')
    await user.selectOptions(screen.getByLabelText('Turno'), 'tarde')
    await user.selectOptions(screen.getByLabelText('Parada'), '5')
    await user.type(screen.getByLabelText(/Observações de cuidado/), 'Alergia a amendoim')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toBeDefined())
    expect(body).toEqual({
      nome: 'Lucas Ferreira',
      data_nascimento: '2015-01-01',
      escola_id: 2,
      turno: 'tarde',
      parada_id: 5,
      observacoes_cuidado: 'Alergia a amendoim',
    })
  })

  it('edit loads the student and sends PUT', async () => {
    mockLookups()
    let body: Record<string, unknown> | undefined
    server.use(
      http.put(`${API}/estudantes/1`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(ESTUDANTE)
      }),
    )
    renderWithRoutes('/students/1/edit', ROUTES, 'gestor')
    const user = userEvent.setup()

    expect(await screen.findByDisplayValue('Lucas Ferreira')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toBeDefined())
    expect(body).toMatchObject({ escola_id: 2, turno: 'tarde', parada_id: 5, observacoes_cuidado: null })
  })
})
