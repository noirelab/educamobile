import { z } from 'zod'
import { todayLocal } from '@/shared/lib/format'

export const enrollSchema = z.object({
  turma_id: z.string().refine((value) => value !== '', 'Informe a turma'),
  data_inicio: z.string().min(1, 'Informe a data de início'),
})

export const transferSchema = z.object({
  turma_destino_id: z.string().refine((value) => value !== '', 'Informe a turma de destino'),
  data: z.string().min(1, 'Informe a data'),
})

export const closeEnrollmentSchema = z.object({
  data_fim: z
    .string()
    .min(1, 'Informe a data de encerramento')
    .refine((value) => value <= todayLocal(), 'A data não pode ser futura'),
})

export type EnrollFormValues = z.infer<typeof enrollSchema>
export type TransferFormValues = z.infer<typeof transferSchema>
export type CloseEnrollmentFormValues = z.infer<typeof closeEnrollmentSchema>
