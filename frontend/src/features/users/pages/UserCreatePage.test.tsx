import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { UserCreatePage } from './UserCreatePage'

const API = 'http://api.test'

const ROUTES = [{ path: '/users', element: <UserCreatePage /> }]

const SCHOOLS = [
  { id: 1, nome: 'EMEF Centro', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
  { id: 7, nome: 'EMEF Sul', codigo_inep: null, endereco: null, polo_id: null, localizacao: null },
]

const SENHA = 'Senha-forte-123'

function mockSchools() {
  server.use(http.get(`${API}/escolas`, () => HttpResponse.json(SCHOOLS)))
}

async function fillBase(user: ReturnType<typeof userEvent.setup>, perfil: string) {
  await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
  await user.type(screen.getByLabelText('E-mail'), 'ana@educa.test')
  await user.selectOptions(screen.getByLabelText('Perfil'), perfil)
}

describe('UserCreatePage', () => {
  it('shows the pending-listing banner', async () => {
    mockSchools()
    renderWithRoutes('/users', ROUTES, 'admin')
    expect(
      await screen.findByText('A listagem e a edição de usuários ainda não estão disponíveis na API'),
    ).toBeInTheDocument()
  })

  it('rejects a password under 10 characters and does not post', async () => {
    mockSchools()
    let called = false
    server.use(
      http.post(`${API}/auth/usuarios`, () => {
        called = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })
    await fillBase(user, 'admin')
    await user.type(screen.getByLabelText('Senha'), 'curta')
    await user.type(screen.getByLabelText('Confirmar senha'), 'curta')
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect((await screen.findAllByText('Mínimo de 10 caracteres')).length).toBeGreaterThan(0)
    expect(called).toBe(false)
  })

  it('rejects a password over 128 characters', async () => {
    mockSchools()
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })
    await fillBase(user, 'admin')
    const senha = 'a'.repeat(129)
    await user.click(screen.getByLabelText('Senha'))
    await user.paste(senha)
    await user.click(screen.getByLabelText('Confirmar senha'))
    await user.paste(senha)
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('Máximo de 128 caracteres')).toBeInTheDocument()
  })

  it('shows As senhas não conferem and does not post', async () => {
    mockSchools()
    let called = false
    server.use(
      http.post(`${API}/auth/usuarios`, () => {
        called = true
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })
    await fillBase(user, 'admin')
    await user.type(screen.getByLabelText('Senha'), SENHA)
    await user.type(screen.getByLabelText('Confirmar senha'), 'Outra-senha-123')
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('As senhas não conferem')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('requires the school only for diretor', async () => {
    mockSchools()
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })

    expect(screen.getByLabelText('Escola')).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Perfil'), 'diretor')
    expect(screen.getByLabelText('Escola')).toBeEnabled()

    await user.type(screen.getByLabelText('Nome'), 'Ana Souza')
    await user.type(screen.getByLabelText('E-mail'), 'ana@educa.test')
    await user.type(screen.getByLabelText('Senha'), SENHA)
    await user.type(screen.getByLabelText('Confirmar senha'), SENHA)
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('Diretor precisa de escola')).toBeInTheDocument()
  })

  it('reacts to typing in the password strength meter', async () => {
    mockSchools()
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })
    await user.type(screen.getByLabelText('Senha'), 'abcdefghij')
    expect(await screen.findByText('Fraca')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Senha'), 'K1-')
    expect(await screen.findByText('Forte')).toBeInTheDocument()
  })

  it('posts the payload, shows the summary and resets with Criar outro', async () => {
    mockSchools()
    let body: unknown
    server.use(
      http.post(`${API}/auth/usuarios`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(
          { id: 9, nome: 'Ana Souza', email: 'ana@educa.test', perfil: 'diretor', escola_id: 7, ativo: true },
          { status: 201 },
        )
      }),
    )
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })
    await fillBase(user, 'diretor')
    await user.selectOptions(screen.getByLabelText('Escola'), '7')
    await user.type(screen.getByLabelText('Senha'), SENHA)
    await user.type(screen.getByLabelText('Confirmar senha'), SENHA)
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('Usuário criado')).toBeInTheDocument()
    expect(body).toEqual({
      nome: 'Ana Souza',
      email: 'ana@educa.test',
      perfil: 'diretor',
      escola_id: 7,
      senha: SENHA,
    })
    const summary = screen.getByText('Usuário criado').closest('section') as HTMLElement
    expect(within(summary).getByText('Ana Souza')).toBeInTheDocument()
    expect(within(summary).getByText('ana@educa.test')).toBeInTheDocument()
    expect(within(summary).getByText('Diretor')).toBeInTheDocument()
    expect(within(summary).getByText('EMEF Sul')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Criar outro' }))
    expect(await screen.findByLabelText('Nome')).toHaveValue('')
    expect(screen.getByLabelText('E-mail')).toHaveValue('')
  })

  it('shows a duplicate email conflict on the email field', async () => {
    mockSchools()
    server.use(
      http.post(`${API}/auth/usuarios`, () => HttpResponse.json({ detail: 'E-mail já cadastrado' }, { status: 409 })),
    )
    renderWithRoutes('/users', ROUTES, 'admin')
    const user = userEvent.setup()
    await screen.findByRole('option', { name: 'EMEF Sul' })
    await fillBase(user, 'coordenador')
    await user.type(screen.getByLabelText('Senha'), SENHA)
    await user.type(screen.getByLabelText('Confirmar senha'), SENHA)
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByText('E-mail já cadastrado')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true'))
  })
})
