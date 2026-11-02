import type { components } from '@/shared/api/schema'
import { ApiError, errorMessage } from '@/shared/api/errors'

type StatusMatricula = components['schemas']['StatusMatricula']

export const ENROLLMENT_STATUS_LABEL: Record<StatusMatricula, string> = {
  ativa: 'Ativa',
  transferida: 'Transferida',
  encerrada: 'Encerrada',
}

export const ENROLLMENT_STATUS_VARIANT: Record<StatusMatricula, 'success' | 'warning' | 'muted'> = {
  ativa: 'success',
  transferida: 'warning',
  encerrada: 'muted',
}

export function enrollmentErrorMessage(e: unknown): string {
  if (e instanceof ApiError && e.detail) return e.detail
  return errorMessage(e)
}
