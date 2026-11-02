import { expect, test, type Page } from '@playwright/test'
import { ADMIN_EMAIL, ADMIN_PASSWORD, apiToken, useStoredToken } from './fixtures'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SCREENS_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '__screens__')
mkdirSync(SCREENS_DIR, { recursive: true })

const WIDTHS = [1440, 1280, 768, 375]
const MENU_PATHS = ['/', '/poles', '/schools', '/classes', '/teachers', '/students', '/attendance', '/stops', '/routes', '/users']

async function assertNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow, 'scrollWidth excede a largura da janela').toBeLessThanOrEqual(0)
}

for (const width of WIDTHS) {
  for (const menuPath of MENU_PATHS) {
    test(`sem rolagem horizontal em ${menuPath} com ${width}px`, async ({ page, request }) => {
      const token = await apiToken(request, ADMIN_EMAIL, ADMIN_PASSWORD)
      await useStoredToken(page, token)
      await page.setViewportSize({ width, height: 860 })
      await page.goto(menuPath)
      await page.waitForLoadState('networkidle')
      await assertNoHorizontalOverflow(page)

      const name = `${width}${menuPath.replace(/\W+/g, '_') || '_root'}.png`
      await page.screenshot({ path: path.join(SCREENS_DIR, name), fullPage: true })
    })
  }
}

test.describe('movimento reduzido', () => {
  test.use({ reducedMotion: 'reduce' })

  test('aurora sem animação em execução', async ({ page, request }) => {
    const token = await apiToken(request, ADMIN_EMAIL, ADMIN_PASSWORD)
    await useStoredToken(page, token)
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const running = await page.evaluate(() => {
      const aurora = document.querySelector('.aurora')
      if (!aurora) throw new Error('elemento .aurora não encontrado')
      return aurora.getAnimations().length
    })
    expect(running).toBe(0)
  })
})
