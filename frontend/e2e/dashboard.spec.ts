import { expect, test } from '@playwright/test'
import { API_URL, apiToken, loginAs, seedScenario, todayLocal } from './fixtures'

test('painel do diretor mostra a infrequência do período', async ({ page, request }) => {
  const scenario = await seedScenario(request)
  const token = await apiToken(request, scenario.diretor.email, scenario.diretor.password)
  const headers = { Authorization: `Bearer ${token}` }
  const hoje = todayLocal()

  const criarEstudante = async (nome: string) => {
    const response = await request.post(`${API_URL}/estudantes`, {
      headers,
      data: {
        nome,
        data_nascimento: '2014-02-01',
        matricula: { turma_id: scenario.turma.id, data_inicio: hoje },
      },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    const estudante = (await response.json()) as { id: number }
    const matriculas = await request.get(`${API_URL}/matriculas?estudante_id=${estudante.id}`, { headers })
    const [matricula] = (await matriculas.json()) as Array<{ id: number }>
    return { matricula_id: matricula.id }
  }

  const matriculaPresente = await criarEstudante(`${scenario.prefix} presente`)
  const matriculaAusente = await criarEstudante(`${scenario.prefix} ausente`)
  const matriculaIdPresente = matriculaPresente.matricula_id
  const matriculaIdAusente = matriculaAusente.matricula_id

  for (const [matricula_id, presenteNaChamada] of [
    [matriculaIdPresente, true],
    [matriculaIdAusente, false],
  ] as const) {
    const response = await request.post(`${API_URL}/frequencias`, {
      headers,
      data: { matricula_id, data: hoje, presente: presenteNaChamada },
    })
    expect(response.ok(), await response.text()).toBeTruthy()
  }

  await loginAs(page, scenario.diretor.email, scenario.diretor.password)
  await page.goto(`/?data_inicio=${hoje}&data_fim=${hoje}`)

  const kpiInfrequencia = page.getByText('Infrequência', { exact: true })
  await expect(kpiInfrequencia).toBeVisible()
  await expect(page.getByText('50,0%').first()).toBeVisible()
})
