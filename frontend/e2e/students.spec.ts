import { expect, test } from '@playwright/test'
import { createStudentViaUi, loginAs, seedScenario } from './fixtures'

test('diretor cadastra estudante com matrícula na turma', async ({ page, request }) => {
  const scenario = await seedScenario(request)
  const nome = `${scenario.prefix} estudante`

  await loginAs(page, scenario.diretor.email, scenario.diretor.password)
  await createStudentViaUi(page, scenario.turma.id, nome)

  await expect(page.getByText('Estudante salvo')).toBeVisible()
  await expect(page.getByRole('heading', { name: nome })).toBeVisible()
})
