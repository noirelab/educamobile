import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { EnrollmentHistory } from './EnrollmentHistory'

const API = 'http://api.test'

const ROUTES = [{ path: '/students/:id', element: <EnrollmentHistory studentId={1} /> }]

const TURMAS_ESCOLA = [
  { id: 3, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 },
  { id: 4, escola_id: 1, nome: '7B', serie: '7º ano', turno: 'tarde', ano_letivo: 2026 },
]

const HISTORICO_ATIVA = [
  { id: 10, estudante_id: 1, turma_id: 2, data_inicio: '2025-02-03', data_fim: '2025-12-15', status: 'transferida' },
  { id: 11, estudante_id: 1, turma_id: 3, data_inicio: '2026-02-03', data_fim: null, status: 'ativa' },
]

const HISTORICO_ENCERRADA = [
  { id: 10, estudante_id: 1, turma_id: 2, data_inicio: '2025-02-03', data_fim: '2025-12-15', status: 'encerrada' },
]

function mockHistory(rows: unknown[]) {
  server.use(
    http.get(`${API}/matriculas/historico/1`, () => HttpResponse.json(rows)),
    http.get(`${API}/turmas`, () => HttpResponse.json(TURMAS_ESCOLA)),
  )
}

describe('EnrollmentHistory', () => {
  it('renders rows in API order with formatted dates and status badges', async () => {
    mockHistory(HISTORICO_ATIVA)
    renderWithRoutes('/students/1', ROUTES, 'admin')

    const rows = await screen.findAllByRole('row')
    expect(within(rows[1]!).getByText('03/02/2025')).toBeInTheDocument()
    expect(within(rows[1]!).getByText('Transferida')).toBeInTheDocument()
    expect(within(rows[2]!).getByText('Ativa')).toBeInTheDocument()
  })

  it('shows transfer and close actions on the active row only', async () => {
    mockHistory(HISTORICO_ATIVA)
    renderWithRoutes('/students/1', ROUTES, 'admin')

    expect(await screen.findByRole('button', { name: 'Transferir' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Encerrar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Matricular' })).not.toBeInTheDocument()
  })

  it('shows Matricular when there is no active enrollment', async () => {
    mockHistory(HISTORICO_ENCERRADA)
    renderWithRoutes('/students/1', ROUTES, 'admin')

    expect(await screen.findByRole('button', { name: 'Matricular' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Transferir' })).not.toBeInTheDocument()
  })

  it('lists only the classes in scope in the transfer dialog and shows the API 403 inside it', async () => {
    mockHistory(HISTORICO_ATIVA)
    server.use(
      http.post(`${API}/matriculas/transferencias`, () =>
        HttpResponse.json({ detail: 'Fora do escopo da sua escola' }, { status: 403 }),
      ),
    )
    renderWithRoutes('/students/1', ROUTES, 'diretor', 1)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Transferir' }))
    const select = await screen.findByLabelText('Turma de destino')
    expect(within(select).getByRole('option', { name: '7B' })).toBeInTheDocument()
    expect(within(select).queryByRole('option', { name: '6A' })).not.toBeInTheDocument()

    await user.selectOptions(select, '4')
    const dataField = screen.getByLabelText('Data')
    await user.clear(dataField)
    await user.type(dataField, '2026-03-10')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Fora do escopo da sua escola')
  })

  it('blocks closing with a future date', async () => {
    mockHistory(HISTORICO_ATIVA)
    let called = false
    server.use(
      http.post(`${API}/matriculas/:id/encerrar`, () => {
        called = true
        return HttpResponse.json(HISTORICO_ATIVA[1])
      }),
    )
    renderWithRoutes('/students/1', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Encerrar' }))
    const field = await screen.findByLabelText('Data de encerramento')
    await user.clear(field)
    await user.type(field, '2999-01-01')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('A data não pode ser futura')).toBeInTheDocument()
    expect(called).toBe(false)
  })
})
