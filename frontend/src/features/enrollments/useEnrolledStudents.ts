import { useQueries, useQuery } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import { getEnrolledStudent, listEnrollments } from './api'

type MatriculaLer = components['schemas']['MatriculaLer']
type EstudanteLer = components['schemas']['EstudanteLer']
type StatusMatricula = components['schemas']['StatusMatricula']

export type EnrolledStudentRow = { matricula: MatriculaLer; estudante: EstudanteLer | undefined }

export function useEnrolledStudents(turmaId: number, status?: StatusMatricula) {
  const enrollments = useQuery({
    queryKey: ['enrollments', 'turma', turmaId, status ?? null],
    queryFn: () =>
      fetchAllPages((limite, deslocamento) => listEnrollments({ turma_id: turmaId, status, limite, deslocamento })),
  })
  const matriculas = enrollments.data ?? []
  const students = useQueries({
    queries: matriculas.map((matricula) => ({
      queryKey: ['students', matricula.estudante_id],
      queryFn: () => getEnrolledStudent(matricula.estudante_id),
    })),
  })

  const rows: EnrolledStudentRow[] = matriculas.map((matricula, index) => ({
    matricula,
    estudante: students[index]?.data,
  }))
  const isLoading = enrollments.isPending || students.some((query) => query.isPending)
  const error = enrollments.error ?? students.find((query) => query.error)?.error ?? null

  return { rows, isLoading, error }
}
