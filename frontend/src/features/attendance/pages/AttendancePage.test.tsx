import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { AttendancePage } from './AttendancePage'

const API = 'http://api.test'
const ROUTES = [{ path: '/attendance', element: <AttendancePage /> }]
const DIA = '2026-10-30'

const TURMAS = [{ id: 1, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 }]

function matriculas(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    estudante_id: index + 1,
    turma_id: 1,
    data_inicio: '2026-02-01',
    data_fim: null,
    status: 'ativa',
  }))
}

function estudantes(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    nome: index === 1 ? 'Bruno Lima' : `Aluno ${index + 1}`,
    data_nascimento: '2015-01-01',
    nome_responsavel: null,
    localizacao: null,
    parada_id: null,
  }))
}

function mockRoll(options: {
  enrollments?: unknown[]
  students?: unknown[]
  existing?: unknown[]
  saveStatus?: { status: number; detail: string }
}) {
  const bodies: unknown[] = []
  server.use(
    http.get(`${API}/turmas`, () => HttpResponse.json(TURMAS)),
    http.get(`${API}/matriculas`, () => HttpResponse.json(options.enrollments ?? matriculas(3))),
    http.get(`${API}/estudantes/:id`, ({ params }) => {
      const found = (options.students ?? estudantes(3)) as { id: number }[]
      return HttpResponse.json(found.find((estudante) => estudante.id === Number(params.id)))
    }),
    http.get(`${API}/frequencias`, () => HttpResponse.json(options.existing ?? [])),
    http.post(`${API}/frequencias/lote`, async ({ request }) => {
      const body = await request.json()
      bodies.push(body)
      if (options.saveStatus) {
        return HttpResponse.json({ detail: options.saveStatus.detail }, { status: options.saveStatus.status })
      }
      return HttpResponse.json([])
    }),
  )
  return bodies
}

function toggleOf(name: string): HTMLElement {
  return screen.getByRole('group', { name: `Frequência de ${name}` })
}

describe('AttendancePage', () => {
  it('shows the empty prompt before a class and date are loaded', async () => {
    mockRoll({})
    renderWithRoutes('/attendance', ROUTES, 'admin')

    expect(await screen.findByText('Escolha a turma e a data para fazer a chamada')).toBeInTheDocument()
  })

  it('blocks a date after today', async () => {
    mockRoll({})
    renderWithRoutes('/attendance', ROUTES, 'admin')

    const amanha = new Date()
    amanha.setDate(amanha.getDate() + 1)
    const future = `${amanha.getFullYear()}-${String(amanha.getMonth() + 1).padStart(2, '0')}-${String(amanha.getDate()).padStart(2, '0')}`
    fireEvent.change(await screen.findByLabelText('Data'), { target: { value: future } })

    expect(screen.getByText('A data não pode ser futura')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Carregar' })).toBeDisabled()
  })

  it('loads the roll from the URL and counts presences and absences', async () => {
    mockRoll({
      enrollments: matriculas(30),
      students: estudantes(30),
      existing: [
        { id: 1, matricula_id: 1, data: DIA, presente: false },
        { id: 2, matricula_id: 2, data: DIA, presente: false },
      ],
    })
    renderWithRoutes(`/attendance?turma=1&data=${DIA}`, ROUTES, 'admin')

    expect(await screen.findByText('28 presentes · 2 faltas')).toBeInTheDocument()
  })

  it('marks every student absent with Todos falta and saves them all', async () => {
    const bodies = mockRoll({ enrollments: matriculas(2), students: estudantes(2) })
    renderWithRoutes(`/attendance?turma=1&data=${DIA}`, ROUTES, 'admin')

    await userEvent.click(await screen.findByRole('button', { name: 'Todos falta' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({
      turma_id: 1,
      data: DIA,
      registros: [
        { matricula_id: 1, presente: false },
        { matricula_id: 2, presente: false },
      ],
    })
  })

  it('shows Atualizar and the Já lançado badge when a record already exists', async () => {
    mockRoll({
      enrollments: matriculas(2),
      students: estudantes(2),
      existing: [{ id: 1, matricula_id: 1, data: DIA, presente: true }],
    })
    renderWithRoutes(`/attendance?turma=1&data=${DIA}`, ROUTES, 'admin')

    expect(await screen.findByRole('button', { name: 'Atualizar' })).toBeInTheDocument()
    expect(screen.getByText('Já lançado')).toBeInTheDocument()
  })

  it('shows the student name when the API rejects the date', async () => {
    mockRoll({
      enrollments: matriculas(3),
      students: estudantes(3),
      saveStatus: { status: 422, detail: 'Data fora do período da matrícula 2' },
    })
    renderWithRoutes(`/attendance?turma=1&data=${DIA}`, ROUTES, 'admin')

    await userEvent.click(await screen.findByRole('button', { name: 'Salvar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Bruno Lima: Data fora do período da matrícula 2')
  })

  it('shows the empty message when the class has no active enrollment on the date', async () => {
    mockRoll({ enrollments: [] })
    renderWithRoutes(`/attendance?turma=1&data=${DIA}`, ROUTES, 'admin')

    expect(await screen.findByText('Nenhum estudante matriculado nesta data')).toBeInTheDocument()
  })

  it('toggles one student to falta and keeps the others present', async () => {
    mockRoll({ enrollments: matriculas(2), students: estudantes(2) })
    renderWithRoutes(`/attendance?turma=1&data=${DIA}`, ROUTES, 'admin')

    await userEvent.click(within(await screen.findByRole('group', { name: 'Frequência de Bruno Lima' })).getByRole('button', { name: 'Falta' }))

    expect(within(toggleOf('Bruno Lima')).getByRole('button', { name: 'Falta' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(toggleOf('Aluno 1')).getByRole('button', { name: 'Presente' })).toHaveAttribute('aria-pressed', 'true')
  })
})
