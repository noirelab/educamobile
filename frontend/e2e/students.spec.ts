import { expect, test } from '@playwright/test'
import { createStudentViaUi, loginAs, seedScenario } from './fixtures'

test('gestor cadastra estudante com escola e turno', async ({ page, request }) => {
  const scenario = await seedScenario(request)
  const nome = `${scenario.prefix} estudante`

  await loginAs(page, scenario.gestor.email, scenario.gestor.password)
  await createStudentViaUi(page, scenario.school.id, nome)

  await expect(page.getByText('Estudante salvo')).toBeVisible()
  await expect(page.getByRole('heading', { name: nome })).toBeVisible()
})
