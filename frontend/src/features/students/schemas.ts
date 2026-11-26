import { z } from 'zod'
import { todayLocal } from '@/shared/lib/format'

export const TURNOS = ['manha', 'tarde', 'integral'] as const
export const TURNO_LABEL: Record<(typeof TURNOS)[number], string> = {
  manha: 'Manhã',
  tarde: 'Tarde',
  integral: 'Integral',
}

export const studentSchema = z.object({
  nome: z.string().trim().min(1, 'Informe o nome'),
  data_nascimento: z
    .string()
    .min(1, 'Informe a data de nascimento')
    .refine((value) => value < todayLocal(), 'A data de nascimento deve estar no passado'),
  escola_id: z.string().min(1, 'Informe a escola'),
  turno: z.enum(TURNOS, { message: 'Informe o turno' }),
  parada_id: z.string(),
  observacoes_cuidado: z.string().trim().max(1000, 'No máximo 1000 caracteres'),
})

export type StudentFormValues = z.infer<typeof studentSchema>
