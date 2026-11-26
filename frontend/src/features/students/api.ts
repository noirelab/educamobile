import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type EstudanteLer = components['schemas']['EstudanteLer']
type EstudantesPagina = components['schemas']['EstudantesPagina']
type EstudanteCriar = components['schemas']['EstudanteCriar']
type ParadaLer = components['schemas']['ParadaLer']

// Reformulação (transporte seguro):
// - Novo: contato de emergência opcional do aluno (`contato_emergencia_nome`, `_telefone`,
//   `_parentesco`) em EstudanteLer e EstudanteCriar. Só a gestão grava, quando o responsável
//   cadastrado pede a troca; o responsável apenas lê em `GET /responsavel/filhos/{id}`.
// - Nome e telefone vão juntos. O telefone volta só com dígitos (ex.: "41999991234").
// - No PUT, campo de contato omitido mantém o valor salvo; mandar os três como null remove.
// - Reformulado: o aluno guarda só o necessário para o transporte (sem endereço da casa);
//   `observacoes_cuidado` só a gestão e a equipe da viagem leem; a foto sai por URL assinada.

type ListParams = { limit: number; offset: number; q?: string }

export function listStudents(p: ListParams) {
  return api<EstudantesPagina>('/estudantes', { query: { limit: p.limit, offset: p.offset, q: p.q || undefined } })
}

export function getStudent(id: number) {
  return api<EstudanteLer>(`/estudantes/${id}`)
}

export function createStudent(body: EstudanteCriar) {
  return api<EstudanteLer>('/estudantes', { method: 'POST', json: body })
}

export function updateStudent(id: number, body: EstudanteCriar) {
  return api<EstudanteLer>(`/estudantes/${id}`, { method: 'PUT', json: body })
}

export function deleteStudent(id: number) {
  return api<void>(`/estudantes/${id}`, { method: 'DELETE' })
}

export function listStopOptions() {
  return api<ParadaLer[]>('/paradas', { query: { limit: 200 } })
}
