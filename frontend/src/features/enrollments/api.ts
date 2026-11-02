import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

type MatriculaLer = components['schemas']['MatriculaLer']
type MatriculaCriar = components['schemas']['MatriculaCriar']
type TransferenciaCriar = components['schemas']['TransferenciaCriar']
type MatriculaEncerrar = components['schemas']['MatriculaEncerrar']
type EstudanteLer = components['schemas']['EstudanteLer']
type StatusMatricula = components['schemas']['StatusMatricula']

export type EnrollmentQuery = {
  turma_id?: number
  estudante_id?: number
  status?: StatusMatricula
  limite?: number
  deslocamento?: number
}

export function listEnrollments(p: EnrollmentQuery) {
  return api<MatriculaLer[]>('/matriculas', {
    query: {
      turma_id: p.turma_id,
      estudante_id: p.estudante_id,
      status: p.status,
      limite: p.limite,
      deslocamento: p.deslocamento,
    },
  })
}

export function enrollmentHistory(studentId: number) {
  return api<MatriculaLer[]>(`/matriculas/historico/${studentId}`)
}

export function createEnrollment(body: MatriculaCriar) {
  return api<MatriculaLer>('/matriculas', { method: 'POST', json: body })
}

export function transfer(body: TransferenciaCriar) {
  return api<MatriculaLer>('/matriculas/transferencias', { method: 'POST', json: body })
}

export function closeEnrollment(id: number, body: MatriculaEncerrar) {
  return api<MatriculaLer>(`/matriculas/${id}/encerrar`, { method: 'POST', json: body })
}

export function getEnrolledStudent(id: number) {
  return api<EstudanteLer>(`/estudantes/${id}`)
}
