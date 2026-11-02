import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { ClassDetailPage } from './ClassDetailPage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/classes/:id', element: <ClassDetailPage /> },
  { path: '/classes', element: <p>Lista de turmas</p> },
  { path: '/classes/:id/edit', element: <p>Editar turma</p> },
]

const TURMA = { id: 1, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 }

const ENROLLMENTS = [
  { id: 11, estudante_id: 20, turma_id: 1, data_inicio: '2026-02-03', data_fim: null, status: 'ativa' },
  { id: 12, estudante_id: 21, turma_id: 1, data_inicio: '2026-03-10', data_fim: null, status: 'ativa' },
]

const STUDENTS: Record<string, { id: number; nome: string }> = {
  '20': { id: 20, nome: 'Lucas Ferreira' },
  '21': { id: 21, nome: 'Marina Costa' },
}

function mockDetail(enrollments: unknown[] = ENROLLMENTS, onEnrollments?: (url: URL) => void) {
  server.use(
    http.get(`${API}/turmas/1`, () => HttpResponse.json(TURMA)),
    http.get(`${API}/escolas`, () =>
      HttpResponse.json([{ id: 1, nome: 'EMEF Centro', codigo_inep: null, endereco: null, polo_id: null, localizacao: null }]),
    ),
    http.get(`${API}/matriculas`, ({ request }) => {
      onEnrollments?.(new URL(request.url))
      return HttpResponse.json(enrollments)
    }),
    http.get(`${API}/estudantes/:id`, ({ params }) => {
      const student = STUDENTS[String(params.id)]
      return HttpResponse.json({
        ...student,
        data_nascimento: '2015-01-01',
        nome_responsavel: null,
        localizacao: null,
        parada_id: null,
      })
    }),
  )
}

describe('ClassDetailPage', () => {
  it('lists active enrollments with student names and dates', async () => {
    const requests: URL[] = []
    mockDetail(ENROLLMENTS, (url) => requests.push(url))
    renderWithRoutes('/classes/1', ROUTES, 'admin')

    expect(await screen.findByRole('link', { name: 'Lucas Ferreira' })).toHaveAttribute('href', '/students/20')
    expect(screen.getByRole('link', { name: 'Marina Costa' })).toHaveAttribute('href', '/students/21')
    expect(screen.getByText('03/02/2026')).toBeInTheDocument()
    expect(requests[0]?.searchParams.get('turma_id')).toBe('1')
    expect(requests[0]?.searchParams.get('status')).toBe('ativa')
  })

  it('shows the empty message when there are no active enrollments', async () => {
    mockDetail([])
    renderWithRoutes('/classes/1', ROUTES, 'admin')

    expect(await screen.findByText('Nenhum estudante matriculado')).toBeInTheDocument()
  })

  it('links Lançar frequência to the attendance page with the class', async () => {
    mockDetail()
    renderWithRoutes('/classes/1', ROUTES, 'diretor', 1)

    expect(await screen.findByRole('link', { name: 'Lançar frequência' })).toHaveAttribute(
      'href',
      '/attendance?turma=1',
    )
  })

  it('hides Lançar frequência and the edit actions for coordenador', async () => {
    mockDetail()
    renderWithRoutes('/classes/1', ROUTES, 'coordenador')

    expect(await screen.findByText('Lucas Ferreira')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Lançar frequência' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
  })
})
