import { z } from 'zod'

export const classSchema = z.object({
  escola_id: z.string().refine((value) => value !== '', 'Informe a escola'),
  nome: z.string().trim().min(1, 'Informe o nome'),
  serie: z.string().trim().min(1, 'Informe a série'),
  turno: z.enum(['manha', 'tarde', 'noite', 'integral']),
  ano_letivo: z
    .string()
    .refine((value) => /^\d{4}$/.test(value) && Number(value) >= 2000 && Number(value) <= 2100, 'Ano letivo entre 2000 e 2100'),
})

export type ClassFormValues = z.infer<typeof classSchema>
