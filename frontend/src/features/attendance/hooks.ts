import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import { listEnrollments } from '@/features/enrollments/api'
import { listAttendance, saveBatch, saveOne } from './api'

type FrequenciaLote = components['schemas']['FrequenciaLote']
type FrequenciaCriar = components['schemas']['FrequenciaCriar']

export type Period = { data_inicio: string; data_fim: string }

export function useAttendanceOn(turmaId: number, day: string) {
  return useQuery({
    queryKey: ['attendance', 'turma', turmaId, day],
    queryFn: () =>
      fetchAllPages((limite, deslocamento) =>
        listAttendance({ turma_id: turmaId, data_inicio: day, data_fim: day, limite, deslocamento }),
      ),
  })
}

export function useStudentAttendance(estudanteId: number, period: Period) {
  return useQuery({
    queryKey: ['attendance', 'student', estudanteId, period.data_inicio, period.data_fim],
    queryFn: () =>
      fetchAllPages((limite, deslocamento) =>
        listAttendance({ estudante_id: estudanteId, data_inicio: period.data_inicio, data_fim: period.data_fim, limite, deslocamento }),
      ),
  })
}

export function useStudentEnrollments(estudanteId: number) {
  return useQuery({
    queryKey: ['enrollments', 'student', estudanteId],
    queryFn: () =>
      fetchAllPages((limite, deslocamento) => listEnrollments({ estudante_id: estudanteId, limite, deslocamento })),
  })
}

function useAttendanceInvalidation() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ['attendance'] })
}

export function useSaveRoll() {
  const invalidate = useAttendanceInvalidation()
  return useMutation({
    mutationFn: (body: FrequenciaLote) => saveBatch(body),
    onSuccess: invalidate,
  })
}

export function useSaveAttendance() {
  const invalidate = useAttendanceInvalidation()
  return useMutation({
    mutationFn: (body: FrequenciaCriar) => saveOne(body),
    onSuccess: invalidate,
  })
}
