import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { getToken } from '@/shared/auth/session'
import { ProfilePage } from './ProfilePage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/profile', element: <ProfilePage /> },
  { path: '/login', element: <p>Tela de login</p> },
]

describe('ProfilePage', () => {
  it('shows the user data from GET /auth/me', async () => {
    renderWithRoutes('/profile', ROUTES, 'gestor')
    expect(await screen.findByRole('heading', { level: 1, name: 'Ana' })).toBeInTheDocument()
    expect(screen.getByText('ana@educa.test')).toBeInTheDocument()
    expect(screen.getAllByText('Gestor de transporte').length).toBeGreaterThan(0)
    expect(screen.queryByText('Escola')).not.toBeInTheDocument()
  })

  it('changes the password and sends the user back to the login', async () => {
    let body: unknown
    server.use(
      http.put(`${API}/auth/senha`, async ({ request }) => {
        body = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithRoutes('/profile', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('heading', { level: 1, name: 'Ana' })
    await user.type(screen.getByLabelText('Senha atual'), 'senha-antiga-1')
    await user.type(screen.getByLabelText('Senha nova'), 'senha-nova-forte-2')
    await user.type(screen.getByLabelText('Confirmar senha nova'), 'senha-nova-forte-2')
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))

    await waitFor(() => expect(getToken()).toBeNull())
    expect(body).toEqual({ senha_atual: 'senha-antiga-1', senha_nova: 'senha-nova-forte-2' })
  })

  it('shows the wrong current password on the field', async () => {
    server.use(
      http.put(`${API}/auth/senha`, () => HttpResponse.json({ detail: 'Senha atual incorreta' }, { status: 403 })),
    )
    renderWithRoutes('/profile', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('heading', { level: 1, name: 'Ana' })
    await user.type(screen.getByLabelText('Senha atual'), 'errada-errada')
    await user.type(screen.getByLabelText('Senha nova'), 'senha-nova-forte-2')
    await user.type(screen.getByLabelText('Confirmar senha nova'), 'senha-nova-forte-2')
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))

    expect(await screen.findByText('Senha atual incorreta')).toBeInTheDocument()
  })

  it('rejects a new password equal to the current one without calling the API', async () => {
    let called = false
    server.use(
      http.put(`${API}/auth/senha`, () => {
        called = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithRoutes('/profile', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('heading', { level: 1, name: 'Ana' })
    await user.type(screen.getByLabelText('Senha atual'), 'mesma-senha-123')
    await user.type(screen.getByLabelText('Senha nova'), 'mesma-senha-123')
    await user.type(screen.getByLabelText('Confirmar senha nova'), 'mesma-senha-123')
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))

    expect(await screen.findByText('A senha nova precisa ser diferente da atual')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('signs out of this device calling /auth/logout with the refresh token', async () => {
    let body: unknown
    sessionStorage.setItem('educamobile.refresh', 'refresh-abc')
    server.use(
      http.post(`${API}/auth/logout`, async ({ request }) => {
        body = await request.json()
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithRoutes('/profile', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('heading', { level: 1, name: 'Ana' })
    await user.click(screen.getByRole('button', { name: 'Sair deste aparelho' }))

    await waitFor(() => expect(getToken()).toBeNull())
    expect(body).toEqual({ refresh_token: 'refresh-abc' })
  })

  it('signs out of every device calling /auth/logout-todos', async () => {
    let called = false
    server.use(
      http.post(`${API}/auth/logout-todos`, () => {
        called = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithRoutes('/profile', ROUTES, 'admin')
    const user = userEvent.setup()

    await screen.findByRole('heading', { level: 1, name: 'Ana' })
    await user.click(screen.getByRole('button', { name: 'Sair de todos os aparelhos' }))

    await waitFor(() => expect(called).toBe(true))
    await waitFor(() => expect(getToken()).toBeNull())
  })
})
