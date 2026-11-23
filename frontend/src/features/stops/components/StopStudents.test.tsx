import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '@/test/server'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { StopStudents } from './StopStudents'

const API = 'http://api.test'

const STUDENT = {
  id: 7,
  nome: 'Ana Lima',
  data_nascimento: '2014-03-02',
  escola_id: 1,
  turno: 'manha',
  observacoes_cuidado: null,
  tem_foto: false,
  parada_id: null,
}

describe('StopStudents', () => {
  it('associates a student through PUT and refreshes the list', async () => {
    let associated = false
    let putCalled = false
    server.use(
      http.get(`${API}/paradas/3/estudantes`, () =>
        HttpResponse.json(associated ? [{ id: 7, nome: 'Ana Lima' }] : []),
      ),
      http.get(`${API}/estudantes`, () => HttpResponse.json({ total: 1, itens: [STUDENT] })),
      http.put(`${API}/paradas/3/estudantes/7`, () => {
        putCalled = true
        associated = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithRoutes('/', [{ path: '/', element: <StopStudents stopId={3} canWrite /> }], 'admin')
    const user = userEvent.setup()

    expect(await screen.findByText('Nenhum estudante associado')).toBeInTheDocument()
    await user.selectOptions(await screen.findByLabelText('Estudante'), '7')
    await user.click(screen.getByRole('button', { name: 'Associar' }))

    await waitFor(() => expect(putCalled).toBe(true))
    const list = await screen.findByRole('list', { name: 'Estudantes da parada' })
    expect(await within(list).findByText('Ana Lima')).toBeInTheDocument()
  })
})
