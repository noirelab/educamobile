import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from '@/shared/api/schema'
import { createEnrollment, closeEnrollment, enrollmentHistory, transfer } from './api'

type MatriculaCriar = components['schemas']['MatriculaCriar']
type TransferenciaCriar = components['schemas']['TransferenciaCriar']
type MatriculaEncerrar = components['schemas']['MatriculaEncerrar']

export function useEnrollmentHistory(studentId: number) {
  return useQuery({
    queryKey: ['enrollments', 'history', studentId],
    queryFn: () => enrollmentHistory(studentId),
  })
}

function useEnrollmentInvalidation() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['enrollments'] }),
      queryClient.invalidateQueries({ queryKey: ['students'] }),
      queryClient.invalidateQueries({ queryKey: ['classes'] }),
    ])
}

export function useCreateEnrollment() {
  const invalidate = useEnrollmentInvalidation()
  return useMutation({
    mutationFn: (body: MatriculaCriar) => createEnrollment(body),
    onSuccess: invalidate,
  })
}

export function useTransfer() {
  const invalidate = useEnrollmentInvalidation()
  return useMutation({
    mutationFn: (body: TransferenciaCriar) => transfer(body),
    onSuccess: invalidate,
  })
}

export function useCloseEnrollment() {
  const invalidate = useEnrollmentInvalidation()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: MatriculaEncerrar }) => closeEnrollment(id, body),
    onSuccess: invalidate,
  })
}
