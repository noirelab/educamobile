import { expect, test } from '@playwright/test'
import { ADMIN_EMAIL, ADMIN_PASSWORD, TOKEN_KEY, loginAs } from './fixtures'

test('login com senha errada mostra erro', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('E-mail', { exact: true }).fill(ADMIN_EMAIL)
  await page.getByLabel('Senha', { exact: true }).fill('senha-errada-e2e-123')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('alert')).toContainText('E-mail ou senha incorretos')
})

test('sessao expirada volta ao login e retorna à página após entrar', async ({ page }) => {
  await loginAs(page, ADMIN_EMAIL, ADMIN_PASSWORD)
  await page.goto('/schools')
  await expect(page.getByRole('heading', { name: 'Escolas' })).toBeVisible()

  await page.evaluate((key) => sessionStorage.removeItem(key), TOKEN_KEY)
  await page.getByRole('link', { name: 'Turmas' }).first().click()

  await expect(page).toHaveURL(/\/login\?expired=1/)
  await expect(page.getByRole('status')).toContainText('Sua sessão expirou. Entre novamente')

  await page.getByLabel('E-mail', { exact: true }).fill(ADMIN_EMAIL)
  await page.getByLabel('Senha', { exact: true }).fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(page).toHaveURL(/\/classes$/)
})
