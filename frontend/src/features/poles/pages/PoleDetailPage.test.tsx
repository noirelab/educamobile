import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { PoleDetailPage } from './PoleDetailPage'

const API = 'http://api.test'

const ROUTES = [
  { path: '/poles/:id', element: <PoleDetailPage /> },
  { path: '/poles', element: <p>Lista de polos</p> },
  { path: '/poles/:id/edit', element: <p>Editar</p> },
]

function mockDetail(deleteResponse: () => Response) {
  server.use(
    http.get(`${API}/polos/1`, () => HttpResponse.json({ id: 1, nome: 'Polo Centro', area: null })),
    http.get(`${API}/escolas`, () => HttpResponse.json([])),
    http.get(`${API}/polos/1/escolas-na-area`, () => HttpResponse.json([])),
    http.delete(`${API}/polos/1`, () => deleteResponse()),
  )
}

describe('PoleDetailPage', () => {
  it('shows the server error inside the confirm dialog when the pole is in use', async () => {
    mockDetail(() => HttpResponse.json({ detail: 'Polo em uso' }, { status: 409 }))
    renderWithRoutes('/poles/1', ROUTES, 'admin')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Excluir' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Excluir' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Polo em uso')
  })

  it('shows Editar and Excluir only for write roles', async () => {
    mockDetail(() => new Response(null, { status: 204 }))
    renderWithRoutes('/poles/1', ROUTES, 'diretor')

    expect(await screen.findByRole('heading', { name: 'Polo Centro' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument()
  })
})
