import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { TeacherListPage } from './TeacherListPage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/teachers', element: <TeacherListPage /> },
  { path: '/teachers/new', element: <p>Novo professor</p> },
  { path: '/teachers/:id/edit', element: <p>Editar professor</p> },
]

const SCHOOLS = [
  { id: 1, nome: 'EMEF Centro', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
  { id: 7, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
]

const TEACHERS = [
  { id: 5, nome: 'Ana Souza', email: 'ana@escola.test', escola_id: 1 },
  { id: 6, nome: 'Bruno Lima', email: 'bruno@escola.test', escola_id: null },
]

function mockLists(teachers: unknown[] = TEACHERS, onRequest?: (url: URL) => void) {
  server.use(
    http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)),
    http.get(`${API}/professores`, ({ request }) => {
      onRequest?.(new URL(request.url))
      return HttpResponse.json(teachers)
    }),
  )
}

describe('TeacherListPage', () => {
  it('lists teachers with email and school name for admin', async () => {
    mockLists()
    renderWithRoutes('/teachers', ROUTES, 'admin')

    expect(await screen.findByText('Ana Souza')).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('ana@escola.test')).toBeInTheDocument()
    expect(within(table).getByText('EMEF Centro')).toBeInTheDocument()
    expect(within(table).getByText('Sem escola')).toBeInTheDocument()
  })

  it('filters by school sending escola_id', async () => {
    const requests: URL[] = []
    mockLists(TEACHERS, (url) => requests.push(url))
    renderWithRoutes('/teachers', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByText('Ana Souza')
    expect(requests[0]?.searchParams.has('escola_id')).toBe(false)

    await user.selectOptions(screen.getByLabelText('Escola'), '7')

    await waitFor(() => expect(requests.at(-1)?.searchParams.get('escola_id')).toBe('7'))
  })

  it('scopes diretor to the own school with no filter and no school column', async () => {
    const requests: URL[] = []
    mockLists(TEACHERS, (url) => requests.push(url))
    renderWithRoutes('/teachers', ROUTES, 'diretor', 7)

    expect(await screen.findByText('Ana Souza')).toBeInTheDocument()
    expect(screen.getByText('Professores da sua escola')).toBeInTheDocument()
    expect(requests.at(-1)?.searchParams.get('escola_id')).toBe('7')
    expect(screen.queryByLabelText('Escola')).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Escola' })).not.toBeInTheDocument()
  })

  it('shows Novo professor for write roles', async () => {
    mockLists()
    renderWithRoutes('/teachers', ROUTES, 'admin')

    expect(await screen.findByRole('link', { name: 'Novo professor' })).toBeInTheDocument()
  })

  it('deletes a teacher after confirmation', async () => {
    mockLists()
    let deleted = false
    server.use(
      http.delete(`${API}/professores/5`, () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithRoutes('/teachers', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByText('Ana Souza')
    await user.click(screen.getByRole('button', { name: 'Excluir professor Ana Souza' }))
    await user.click(await screen.findByRole('button', { name: 'Excluir' }))

    await waitFor(() => expect(deleted).toBe(true))
  })

  it('shows the empty message when there are no teachers', async () => {
    mockLists([])
    renderWithRoutes('/teachers', ROUTES, 'admin')

    expect(await screen.findByText('Nenhum professor cadastrado')).toBeInTheDocument()
  })
})
