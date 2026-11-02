import { expect, test } from '@playwright/test'
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAs, seedScenario, uniquePrefix, useStoredToken, apiToken } from './fixtures'

test('páginas acessadas diretamente carregam sem voltar ao login', async ({ page, request }) => {
  const token = await apiToken(request, ADMIN_EMAIL, ADMIN_PASSWORD)
  await useStoredToken(page, token)

  await page.goto('/schools')
  await expect(page).toHaveURL(/\/schools$/)
  await expect(page.getByRole('heading', { name: 'Escolas' })).toBeVisible()

  await page.goto('/students')
  await expect(page).toHaveURL(/\/students$/)
  await expect(page.getByRole('heading', { name: 'Estudantes' })).toBeVisible()
})

test('endereço inexistente mostra a página de não encontrado', async ({ page, request }) => {
  const token = await apiToken(request, ADMIN_EMAIL, ADMIN_PASSWORD)
  await useStoredToken(page, token)

  await page.goto('/nao-existe-e2e')
  await expect(page.getByRole('heading', { name: 'Página não encontrada' })).toBeVisible()
})

test('coordenador monta rota com três paradas e vê a distância em metros', async ({ page, request }) => {
  const scenario = await seedScenario(request)
  const nomeRota = `${uniquePrefix()} rota`

  await loginAs(page, scenario.coordenador.email, scenario.coordenador.password)
  await page.goto('/routes')
  await page.getByRole('button', { name: 'Nova rota' }).click()
  await page.getByLabel('Nome', { exact: true }).fill(nomeRota)
  await page.getByRole('button', { name: 'Criar', exact: true }).click()

  await expect(page.getByRole('heading', { name: nomeRota })).toBeVisible()

  for (const parada of scenario.paradas) {
    await page.getByTitle(parada.nome, { exact: true }).dispatchEvent('click')
  }
  await expect(page.locator('ol[aria-label="Sequência de paradas"]')).toBeVisible()

  await page.getByRole('button', { name: 'Salvar sequência' }).click()

  await expect(page.getByText('→', { exact: false }).last()).toContainText(/\d[\d.,]* m$/)
})
