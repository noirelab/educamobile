import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { StopStudents } from './StopStudents'

const API = 'http://api.test'

describe('StopStudents', () => {
  it('lists the students of the stop and offers no way to attach them', async () => {
    server.use(http.get(`${API}/paradas/3/estudantes`, () => HttpResponse.json([{ id: 7, nome: 'Ana Lima' }])))
    renderWithRoutes('/', [{ path: '/', element: <StopStudents stopId={3} /> }], 'admin')

    const list = await screen.findByRole('list', { name: 'Estudantes da parada' })
    expect(within(list).getByText('Ana Lima')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Associar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remover' })).not.toBeInTheDocument()
  })

  it('shows the empty message', async () => {
    server.use(http.get(`${API}/paradas/3/estudantes`, () => HttpResponse.json([])))
    renderWithRoutes('/', [{ path: '/', element: <StopStudents stopId={3} /> }], 'admin')

    expect(await screen.findByText('Nenhum estudante nesta parada')).toBeInTheDocument()
  })
})
