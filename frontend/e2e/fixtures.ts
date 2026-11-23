import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const API_URL = 'http://localhost:8000'
export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? ''
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? ''
export const TOKEN_KEY = 'educamobile.token'
export const REFRESH_KEY = 'educamobile.refresh'
export const SCENARIO_PASSWORD = 'senha-e2e-2026-segura'

type Coordinates = { latitude: number; longitude: number }
type IdRecord = { id: number }

export type Scenario = {
  prefix: string
  school: IdRecord & { nome: string }
  gestor: { email: string; password: string }
  paradas: Array<IdRecord & { nome: string; localizacao: Coordinates }>
}

export function uniquePrefix(): string {
  return `E2E ${Date.now()}`
}

export function randomInep(): string {
  return String(Math.floor(10_000_000 + Math.random() * 89_999_999))
}

function randomCoordinates(): Coordinates {
  return {
    latitude: Number((-23.3 - Math.random() * 0.4).toFixed(6)),
    longitude: Number((-51.2 - Math.random() * 0.3).toFixed(6)),
  }
}

export async function loginAs(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('E-mail', { exact: true }).fill(email)
  await page.getByLabel('Senha', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

export async function apiToken(request: APIRequestContext, email: string, password: string): Promise<string> {
  const response = await request.post(`${API_URL}/auth/login`, {
    form: { username: email, password },
  })
  expect(response.ok(), `login de ${email}`).toBeTruthy()
  const body = (await response.json()) as { access_token: string }
  return body.access_token
}

async function apiPost<T>(request: APIRequestContext, token: string, path: string, data: unknown): Promise<T> {
  const response = await request.post(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    data,
  })
  expect(response.ok(), `POST ${path}: ${await response.text()}`).toBeTruthy()
  return (await response.json()) as T
}

export async function seedScenario(request: APIRequestContext): Promise<Scenario> {
  const adminToken = await apiToken(request, ADMIN_EMAIL, ADMIN_PASSWORD)
  const prefix = uniquePrefix()
  const stamp = Date.now()

  const school = await apiPost<IdRecord & { nome: string }>(request, adminToken, '/escolas', {
    nome: `${prefix} escola`,
    codigo_inep: randomInep(),
    endereco: 'Rua E2E, 100',
    localizacao: randomCoordinates(),
  })

  const gestor = { email: `e2e-${stamp}-gestor@exemplo.com`, password: SCENARIO_PASSWORD }
  await apiPost(request, adminToken, '/usuarios', {
    nome: `${prefix} gestor`,
    email: gestor.email,
    senha: gestor.password,
    perfil: 'gestor',
  })

  const center = randomCoordinates()
  const paradas: Scenario['paradas'] = []
  for (const [index, offset] of [0, 0.05, 0.1].entries()) {
    const localizacao = { latitude: center.latitude + offset, longitude: center.longitude + offset / 2 }
    const parada = await apiPost<IdRecord & { nome: string }>(request, adminToken, '/paradas', {
      nome: `${prefix} parada ${index + 1}`,
      localizacao,
    })
    paradas.push({ ...parada, localizacao })
  }

  return { prefix, school, gestor, paradas }
}

export async function createStudentViaUi(page: Page, escolaId: number, nome: string): Promise<void> {
  await page.goto('/students/new')
  await page.getByLabel('Nome', { exact: true }).fill(nome)
  await page.getByLabel('Data de nascimento').fill('2015-03-10')
  await page.getByLabel('Escola').selectOption(String(escolaId))
  await page.getByLabel('Turno').selectOption('manha')
  await page.getByRole('button', { name: 'Salvar', exact: true }).click()
  await expect(page).toHaveURL(/\/students\/\d+$/)
}

export async function useStoredToken(page: Page, token: string): Promise<void> {
  await page.addInitScript(
    ([key, value]) => sessionStorage.setItem(key, value),
    [TOKEN_KEY, token] as const,
  )
}
