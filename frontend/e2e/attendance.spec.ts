import { expect, test } from '@playwright/test'
import { API_URL, apiToken, loginAs, seedScenario, todayLocal } from './fixtures'

test('diretor faz a chamada da turma e registra falta', async ({ page, request }) => {
  const scenario = await seedScenario(request)
  const token = await apiToken(request, scenario.diretor.email, scenario.diretor.password)
  const nome = `${scenario.prefix} chamada`
  const student = await request.post(`${API_URL}/estudantes`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      nome,
      data_nascimento: '2014-06-01',
      matricula: { turma_id: scenario.turma.id, data_inicio: todayLocal() },
    },
  })
  expect(student.ok(), await student.text()).toBeTruthy()

  await loginAs(page, scenario.diretor.email, scenario.diretor.password)
  await page.goto(`/attendance?turma=${scenario.turma.id}&data=${todayLocal()}`)

  const group = page.getByRole('group', { name: `Frequência de ${nome}` })
  await expect(group).toBeVisible()
  await group.getByRole('button', { name: 'Falta' }).click()
  await page.getByRole('button', { name: 'Salvar', exact: true }).click()

  await expect(page.getByText('Frequência salva')).toBeVisible()
  await expect(group.getByRole('button', { name: 'Falta' })).toHaveAttribute('aria-pressed', 'true')
})
