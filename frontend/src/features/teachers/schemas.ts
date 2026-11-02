import { z } from 'zod'

export const teacherSchema = z.object({
  nome: z.string().trim().min(1, 'Informe o nome'),
  email: z.string().trim().email('E-mail inválido'),
  escola_id: z.string(),
})

export type TeacherFormValues = z.infer<typeof teacherSchema>
