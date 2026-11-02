import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { NearbySearch } from './NearbySearch'

const API = 'http://api.test'

function routesWith(onSearch: () => void) {
  return [{ path: '/', element: <NearbySearch prefill={null} onSearch={onSearch} /> }]
}

async function fillPoint(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Latitude'), '-25.43')
  await user.type(screen.getByLabelText('Longitude'), '-49.27')
}

describe('NearbySearch', () => {
  it('rejects a radius above 50 km without calling the API', async () => {
    const request = vi.fn()
    server.use(
      http.get(`${API}/paradas/proximas`, () => {
        request()
        return HttpResponse.json([])
      }),
    )
    renderWithRoutes('/', routesWith(() => {}), 'admin')
    const user = userEvent.setup()

    await fillPoint(user)
    await user.clear(screen.getByLabelText('Raio (m)'))
    await user.type(screen.getByLabelText('Raio (m)'), '60000')
    await user.click(screen.getByRole('button', { name: 'Buscar próximas' }))

    expect(await screen.findByText('Raio máximo de 50 km')).toBeInTheDocument()
    expect(request).not.toHaveBeenCalled()
  })

  it('lists nearby stops with formatted distances', async () => {
    let radius: string | null = null
    server.use(
      http.get(`${API}/paradas/proximas`, ({ request }) => {
        radius = new URL(request.url).searchParams.get('raio_m')
        return HttpResponse.json([
          { id: 1, nome: 'Parada Centro', localizacao: { latitude: -25.43, longitude: -49.27 }, distancia_m: 350 },
        ])
      }),
    )
    renderWithRoutes('/', routesWith(() => {}), 'admin')
    const user = userEvent.setup()

    await fillPoint(user)
    await user.click(screen.getByRole('button', { name: 'Buscar próximas' }))

    expect(await screen.findByText('Parada Centro — 350 m')).toBeInTheDocument()
    expect(radius).toBe('1000')
  })

  it('shows the empty message when no stop is within the radius', async () => {
    server.use(http.get(`${API}/paradas/proximas`, () => HttpResponse.json([])))
    renderWithRoutes('/', routesWith(() => {}), 'admin')
    const user = userEvent.setup()

    await fillPoint(user)
    await user.click(screen.getByRole('button', { name: 'Buscar próximas' }))

    expect(await screen.findByText('Nenhuma parada neste raio')).toBeInTheDocument()
  })
})
