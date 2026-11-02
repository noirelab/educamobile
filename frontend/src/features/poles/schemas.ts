import { z } from 'zod'

export const poleSchema = z.object({
  nome: z.string().trim().min(1, 'Informe o nome'),
})

export type PoleFormValues = z.infer<typeof poleSchema>
