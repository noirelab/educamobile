import { z } from 'zod'
import { todayLocal } from '@/shared/lib/format'

const MATRICULA_REQUIRED = 'Informe a turma e a data de início'

type StudentSchemaOptions = { isCreate: boolean; isDiretor: boolean }

export function buildStudentSchema({ isCreate, isDiretor }: StudentSchemaOptions) {
  return z
    .object({
      nome: z.string().trim().min(1, 'Informe o nome'),
      data_nascimento: z
        .string()
        .min(1, 'Informe a data de nascimento')
        .refine((value) => value < todayLocal(), 'A data de nascimento deve estar no passado'),
      nome_responsavel: z.string().trim(),
      localizacao: z.object({ latitude: z.number(), longitude: z.number() }).nullable(),
      turma_id: z.string(),
      data_inicio: z.string(),
      parada_id: z.string(),
    })
    .superRefine((values, ctx) => {
      if (!isCreate) return
      const hasTurma = values.turma_id !== ''
      const hasInicio = values.data_inicio !== ''
      if (isDiretor && !hasTurma && !hasInicio) {
        ctx.addIssue({ code: 'custom', path: ['turma_id'], message: MATRICULA_REQUIRED })
        return
      }
      if (hasTurma && !hasInicio) {
        ctx.addIssue({ code: 'custom', path: ['data_inicio'], message: 'Informe a data de início' })
      }
      if (isDiretor && !hasTurma) {
        ctx.addIssue({ code: 'custom', path: ['turma_id'], message: 'Informe a turma' })
      }
    })
}

export type StudentFormValues = z.infer<ReturnType<typeof buildStudentSchema>>
