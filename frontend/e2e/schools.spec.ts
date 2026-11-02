import { expect, test } from '@playwright/test'
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAs, randomInep, uniquePrefix } from './fixtures'

test('admin cria escola marcando o ponto no mapa', async ({ page }) => {
  const nome = `${uniquePrefix()} escola criada`

  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await page.goto('/schools/new')

  await page.getByLabel('Nome', { exact: true }).fill(nome)
  await page.getByLabel('Código INEP').fill(randomInep())

  const map = page.locator('.leaflet-container').first()
  await expect(map).toBeVisible()
  const box = await map.boundingBox()
  if (!box) throw new Error('mapa sem dimensões')
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)

  await expect(page.getByLabel('Latitude', { exact: true })).not.toHaveValue('')
  await expect(page.getByLabel('Longitude', { exact: true })).not.toHaveValue('')

  await page.getByRole('button', { name: 'Salvar', exact: true }).click()

  await expect(page).toHaveURL(/\/schools\/\d+$/)
  await expect(page.getByText('Escola salva')).toBeVisible()
  await expect(page.getByRole('heading', { name: nome })).toBeVisible()
})
