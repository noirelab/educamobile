import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { PoleFormPage } from './PoleFormPage'

const API = 'http://api.test'

const { DRAWN_AREA } = vi.hoisted(() => ({
  DRAWN_AREA: {
    type: 'MultiPolygon' as const,
    coordinates: [
      [
        [
          [-49.27, -25.43],
          [-49.26, -25.43],
          [-49.26, -25.42],
          [-49.27, -25.42],
          [-49.27, -25.43],
        ],
      ],
    ],
  },
}))

vi.mock('@/features/poles/components/AreaEditor', () => ({
  AreaEditor: ({ onChange }: { onChange: (area: unknown) => void }) => (
    <div>
      <button type="button" onClick={() => onChange(DRAWN_AREA)}>
        Desenhar área de teste
      </button>
      <button type="button" onClick={() => onChange(null)}>
        Limpar área
      </button>
    </div>
  ),
}))

const ROUTES = [
  { path: '/poles/new', element: <PoleFormPage /> },
  { path: '/poles/:id/edit', element: <PoleFormPage /> },
  { path: '/poles/:id', element: <p>Detalhe do polo</p> },
]

describe('PoleFormPage', () => {
  it('posts nome and the drawn area', async () => {
    let body: unknown
    server.use(
      http.post(`${API}/polos`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 7, nome: 'Polo Norte', area: DRAWN_AREA }, { status: 201 })
      }),
    )
    renderWithRoutes('/poles/new', ROUTES)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Nome'), 'Polo Norte')
    await user.click(screen.getByRole('button', { name: 'Desenhar área de teste' }))
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toEqual({ nome: 'Polo Norte', area: DRAWN_AREA }))
  })

  it('blocks submit with an empty nome', async () => {
    let called = false
    server.use(
      http.post(`${API}/polos`, () => {
        called = true
        return HttpResponse.json({ id: 1, nome: '', area: null }, { status: 201 })
      }),
    )
    renderWithRoutes('/poles/new', ROUTES)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Informe o nome')).toBeInTheDocument()
    expect(called).toBe(false)
  })

  it('posts area null after Limpar área', async () => {
    let body: unknown
    server.use(
      http.get(`${API}/polos/5`, () =>
        HttpResponse.json({ id: 5, nome: 'Polo Leste', area: DRAWN_AREA }),
      ),
      http.put(`${API}/polos/5`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 5, nome: 'Polo Leste', area: null })
      }),
    )
    renderWithRoutes('/poles/5/edit', ROUTES)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Limpar área' }))
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toEqual({ nome: 'Polo Leste', area: null }))
  })

  it('shows the geometry error above the map with role alert', async () => {
    server.use(
      http.post(`${API}/polos`, () =>
        HttpResponse.json(
          { detail: 'Geometria inválida, por exemplo, com autointerseção' },
          { status: 422 },
        ),
      ),
    )
    renderWithRoutes('/poles/new', ROUTES)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Nome'), 'Polo Norte')
    await user.click(screen.getByRole('button', { name: 'Desenhar área de teste' }))
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Geometria inválida, por exemplo, com autointerseção',
    )
  })

  it('loads the pole and sends PUT on edit', async () => {
    let body: unknown
    server.use(
      http.get(`${API}/polos/3`, () =>
        HttpResponse.json({ id: 3, nome: 'Polo Sul', area: null }),
      ),
      http.put(`${API}/polos/3`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ id: 3, nome: 'Polo Sul II', area: null })
      }),
    )
    renderWithRoutes('/poles/3/edit', ROUTES)
    const user = userEvent.setup()

    expect(await screen.findByRole('heading', { name: 'Editar polo' })).toBeInTheDocument()
    const nome = screen.getByLabelText('Nome')
    await user.clear(nome)
    await user.type(nome, 'Polo Sul II')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(body).toEqual({ nome: 'Polo Sul II', area: null }))
  })
})
