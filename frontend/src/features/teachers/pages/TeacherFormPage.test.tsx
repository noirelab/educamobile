import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { TeacherFormPage } from './TeacherFormPage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/teachers/new', element: <TeacherFormPage /> },
  { path: '/teachers/:id/edit', element: <TeacherFormPage /> },
  { path: '/teachers', element: <p>Lista de professores</p> },
]

const SCHOOLS = [
  { id: 1, nome: 'EMEF Centro', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
  { id: 7, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
]

function mockSchools() {
  server.use(http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)))
}

describe('TeacherFormPage', () => {
  it('lowercases the email before posting', async () => {
    mockSchools()
    let body: unknown
    server.use(
      http.post(`${API}/professores`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    renderWithRoutes('/teachers/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Sul' })
    await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
    await user.type(screen.getByLabelText('E-mail'), '  Ana.Souza@Escola.TEST ')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toEqual({ nome: 'Ana Souza', email: 'ana.souza@escola.test', escola_id: null }))
  })

  it('shows E-mail inválido and does not post', async () => {
    mockSchools()
    let called = false
    server.use(
      http.post(`${API}/professores`, () => {
        called = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    renderWithRoutes('/teachers/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Sul' })
    await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
    await user.type(screen.getByLabelText('E-mail'), 'ana-sem-arroba')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('E-mail inválido')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('posts the chosen school for admin', async () => {
    mockSchools()
    let body: unknown
    server.use(
      http.post(`${API}/professores`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    renderWithRoutes('/teachers/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Sul' })
    await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
    await user.type(screen.getByLabelText('E-mail'), 'ana@escola.test')
    await user.selectOptions(screen.getByLabelText('Escola'), '7')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toEqual({ nome: 'Ana Souza', email: 'ana@escola.test', escola_id: 7 }))
  })

  it('locks the school to the diretor own school', async () => {
    mockSchools()
    let body: unknown
    server.use(
      http.post(`${API}/professores`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 9 }, { status: 201 })
      }),
    )
    renderWithRoutes('/teachers/new', ROUTES, 'diretor', 7)
    const user = userEvent.setup()

    const escola = await screen.findByLabelText('Escola')
    expect(escola).toBeDisabled()
    expect(escola).toHaveValue('7')
    await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
    await user.type(screen.getByLabelText('E-mail'), 'ana@escola.test')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toMatchObject({ escola_id: 7 }))
  })

  it('shows the duplicate email conflict on the email field', async () => {
    mockSchools()
    server.use(
      http.post(`${API}/professores`, () =>
        HttpResponse.json({ detail: 'E-mail já cadastrado' }, { status: 409 }),
      ),
    )
    renderWithRoutes('/teachers/new', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('option', { name: 'EMEF Sul' })
    await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
    await user.type(screen.getByLabelText('E-mail'), 'ana@escola.test')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('E-mail já cadastrado')).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true')
  })

  it('loads the teacher and sends PUT on edit', async () => {
    mockSchools()
    let body: unknown
    const saved = vi.fn()
    server.use(
      http.get(`${API}/professores/5`, () =>
        HttpResponse.json({ id: 5, nome: 'Ana Souza', email: 'ana@escola.test', escola_id: 1 }),
      ),
      http.put(`${API}/professores/5`, async ({ request }) => {
        saved()
        body = await request.json()
        return HttpResponse.json({ id: 5 })
      }),
    )
    renderWithRoutes('/teachers/5/edit', ROUTES, 'admin')
    const user = userEvent.setup()

    expect(await screen.findByRole('heading', { name: 'Editar professor' })).toBeInTheDocument()
    const nome = screen.getByLabelText('Nome')
    await user.clear(nome)
    await user.type(nome, 'Ana Lima')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() =>
      expect(body).toEqual({ nome: 'Ana Lima', email: 'ana@escola.test', escola_id: 1 }),
    )
  })
})
