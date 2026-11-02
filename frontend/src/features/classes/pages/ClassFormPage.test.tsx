import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { ClassFormPage } from './ClassFormPage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/classes/new', element: <ClassFormPage /> },
  { path: '/classes/:id/edit', element: <ClassFormPage /> },
  { path: '/classes/:id', element: <p>Detalhe da turma</p> },
]

const SCHOOLS = [
  { id: 1, nome: 'EMEF Centro', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
  { id: 7, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
]

function mockSchools() {
  server.use(http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)))
}

describe('ClassFormPage', () => {
  it('defaults ano letivo to the current year', async () => {
    mockSchools()
    renderWithRoutes('/classes/new', ROUTES)

    expect(await screen.findByLabelText('Ano letivo')).toHaveValue(new Date().getFullYear())
  })

  it('rejects ano letivo 1999 and does not post', async () => {
    mockSchools()
    let called = false
    server.use(
      http.post(`${API}/turmas`, () => {
        called = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    renderWithRoutes('/classes/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Centro' })
    await user.selectOptions(screen.getByLabelText('Escola'), '1')
    await user.type(screen.getByLabelText('Nome'), '6A')
    await user.type(screen.getByLabelText('Série'), '6º ano')
    const ano = screen.getByLabelText('Ano letivo')
    await user.clear(ano)
    await user.type(ano, '1999')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Ano letivo entre 2000 e 2100')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('posts the typed values for admin', async () => {
    mockSchools()
    let body: unknown
    server.use(
      http.post(`${API}/turmas`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    renderWithRoutes('/classes/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Sul' })
    await user.selectOptions(screen.getByLabelText('Escola'), '7')
    await user.type(screen.getByLabelText('Nome'), '6A')
    await user.type(screen.getByLabelText('Série'), '6º ano')
    await user.selectOptions(screen.getByLabelText('Turno'), 'tarde')
    await user.clear(screen.getByLabelText('Ano letivo'))
    await user.type(screen.getByLabelText('Ano letivo'), '2027')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() =>
      expect(body).toEqual({ escola_id: 7, nome: '6A', serie: '6º ano', turno: 'tarde', ano_letivo: 2027 }),
    )
  })

  it('locks the school to the diretor own school', async () => {
    mockSchools()
    let body: unknown
    server.use(
      http.post(`${API}/turmas`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    renderWithRoutes('/classes/new', ROUTES, 'diretor', 7)
    const user = userEvent.setup()

    const escola = await screen.findByLabelText('Escola')
    expect(escola).toBeDisabled()
    expect(escola).toHaveValue('7')
    await user.type(screen.getByLabelText('Nome'), '6A')
    await user.type(screen.getByLabelText('Série'), '6º ano')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toMatchObject({ escola_id: 7 }))
  })

  it('loads the class and sends PUT on edit', async () => {
    mockSchools()
    let body: unknown
    const saved = vi.fn()
    server.use(
      http.get(`${API}/turmas/5`, () =>
        HttpResponse.json({ id: 5, escola_id: 1, nome: '6A', serie: '6º ano', turno: 'manha', ano_letivo: 2026 }),
      ),
      http.put(`${API}/turmas/5`, async ({ request }) => {
        saved()
        body = await request.json()
        return HttpResponse.json({ id: 5 })
      }),
    )
    renderWithRoutes('/classes/5/edit', ROUTES, 'admin')
    const user = userEvent.setup()

    expect(await screen.findByRole('heading', { name: 'Editar turma' })).toBeInTheDocument()
    const nome = screen.getByLabelText('Nome')
    await user.clear(nome)
    await user.type(nome, '6B')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() =>
      expect(body).toEqual({ escola_id: 1, nome: '6B', serie: '6º ano', turno: 'manha', ano_letivo: 2026 }),
    )
  })
})
