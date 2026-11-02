import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { StudentAttendance } from './StudentAttendance'

const API = 'http://api.test'
const ROUTES = [{ path: '/students/:id', element: <StudentAttendance studentId={5} /> }]

const TURMAS = [{ id: 3, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 }]

const MATRICULAS = [
  { id: 10, estudante_id: 5, turma_id: 3, data_inicio: '2026-02-03', data_fim: null, status: 'ativa' },
]

const REGISTROS = Array.from({ length: 20 }, (_, index) => ({
  id: index + 1,
  matricula_id: 10,
  data: `2026-10-${String(index + 1).padStart(2, '0')}`,
  presente: ![2, 9, 15].includes(index),
}))

async function rowWith(text: string): Promise<HTMLElement> {
  const cell = await screen.findByText(text)
  const row = cell.closest('tr')
  if (!row) throw new Error(`row with ${text} not found`)
  return row
}

describe('StudentAttendance', () => {
  it('lists the period records with date, class and situation and sums the absences', async () => {
    const requests: URL[] = []
    server.use(
      http.get(`${API}/frequencias`, ({ request }) => {
        requests.push(new URL(request.url))
        return HttpResponse.json(REGISTROS)
      }),
      http.get(`${API}/matriculas`, () => HttpResponse.json(MATRICULAS)),
      http.get(`${API}/turmas`, () => HttpResponse.json(TURMAS)),
    )
    renderWithRoutes('/students/5', ROUTES, 'admin')

    expect(await screen.findByText('3 faltas em 20 registros')).toBeInTheDocument()
    const falta = await rowWith('03/10/2026')
    expect(await within(falta).findByText('6A')).toBeInTheDocument()
    expect(within(falta).getByRole('button', { name: 'Falta', pressed: true })).toBeInTheDocument()
    expect(requests[0]?.searchParams.get('estudante_id')).toBe('5')
    expect(requests[0]?.searchParams.get('data_inicio')).not.toBeNull()
    expect(requests[0]?.searchParams.get('data_fim')).not.toBeNull()
  })

  it('posts the correction with the matricula and date when a row is toggled', async () => {
    const bodies: unknown[] = []
    server.use(
      http.get(`${API}/frequencias`, () => HttpResponse.json(REGISTROS)),
      http.get(`${API}/matriculas`, () => HttpResponse.json(MATRICULAS)),
      http.get(`${API}/turmas`, () => HttpResponse.json(TURMAS)),
      http.post(`${API}/frequencias`, async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json({ id: 3, matricula_id: 10, data: '2026-10-03', presente: true })
      }),
    )
    renderWithRoutes('/students/5', ROUTES, 'admin')

    await screen.findByText('3 faltas em 20 registros')
    await userEvent.click(within(await rowWith('03/10/2026')).getByRole('button', { name: 'Presente' }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toEqual({ matricula_id: 10, data: '2026-10-03', presente: true })
  })
})
