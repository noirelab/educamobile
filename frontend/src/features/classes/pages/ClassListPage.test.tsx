import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { ClassListPage } from './ClassListPage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/classes', element: <ClassListPage /> },
  { path: '/classes/new', element: <p>Nova turma</p> },
  { path: '/classes/:id', element: <p>Detalhe</p> },
]

const SCHOOLS = [
  { id: 1, nome: 'EMEF Centro', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
  { id: 7, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
]

const CLASSES = [
  { id: 5, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 },
  { id: 6, escola_id: 7, nome: '7B', serie: '7º ano', turno: 'integral', ano_letivo: 2026 },
]

function mockLists(classes: unknown[] = CLASSES, onClassesRequest?: (url: URL) => void) {
  server.use(
    http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)),
    http.get(`${API}/turmas`, ({ request }) => {
      onClassesRequest?.(new URL(request.url))
      return HttpResponse.json(classes)
    }),
  )
}

describe('ClassListPage', () => {
  it('lists classes with turno label and school name for admin', async () => {
    mockLists()
    renderWithRoutes('/classes', ROUTES, 'admin')

    expect(await screen.findByText('6A')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('Manhã')).toBeInTheDocument()
    expect(within(table).getByText('Integral')).toBeInTheDocument()
    expect(within(table).getByText('EMEF Sul')).toBeInTheDocument()
  })

  it('filters by school sending escola_id and resets the page', async () => {
    const requests: URL[] = []
    mockLists(CLASSES, (url) => requests.push(url))
    renderWithRoutes('/classes', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByText('6A')
    expect(requests[0]?.searchParams.has('escola_id')).toBe(false)

    await user.selectOptions(screen.getByLabelText('Escola'), '7')

    await waitFor(() => expect(requests.at(-1)?.searchParams.get('escola_id')).toBe('7'))
  })

  it('scopes diretor to the own school with no filter and no school column', async () => {
    const requests: URL[] = []
    mockLists(CLASSES, (url) => requests.push(url))
    renderWithRoutes('/classes', ROUTES, 'diretor', 7)

    expect(await screen.findByText('6A')).toBeInTheDocument()
    expect(screen.getByText('Turmas da sua escola')).toBeInTheDocument()
    expect(requests.at(-1)?.searchParams.get('escola_id')).toBe('7')
    expect(screen.queryByLabelText('Escola')).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Escola' })).not.toBeInTheDocument()
  })

  it('shows Nova turma for write roles only', async () => {
    mockLists()
    renderWithRoutes('/classes', ROUTES, 'admin')

    expect(await screen.findByRole('link', { name: 'Nova turma' })).toBeInTheDocument()
  })

  it('hides Nova turma for coordenador', async () => {
    mockLists()
    renderWithRoutes('/classes', ROUTES, 'coordenador')

    expect(await screen.findByText('6A')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nova turma' })).not.toBeInTheDocument()
  })

  it('shows the empty message when there are no classes', async () => {
    mockLists([])
    renderWithRoutes('/classes', ROUTES, 'admin')

    expect(await screen.findByText('Nenhuma turma cadastrada')).toBeInTheDocument()
  })
})
