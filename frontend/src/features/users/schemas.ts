import { z } from 'zod'

const PERFIS = ['admin', 'diretor', 'coordenador'] as const

export const userCreateSchema = z
  .object({
    nome: z.string().trim().min(1, 'Informe o nome'),
    email: z.string().trim().email('E-mail inválido'),
    perfil: z.string().refine((value) => (PERFIS as readonly string[]).includes(value), 'Informe o perfil'),
    escola_id: z.string(),
    senha: z
      .string()
      .min(10, 'Mínimo de 10 caracteres')
      .max(128, 'Máximo de 128 caracteres'),
    confirmar_senha: z.string(),
  })
  .superRefine((values, ctx) => {
    if (values.perfil === 'diretor' && values.escola_id === '') {
      ctx.addIssue({ code: 'custom', path: ['escola_id'], message: 'Diretor precisa de escola' })
    }
    if (values.senha !== values.confirmar_senha) {
      ctx.addIssue({ code: 'custom', path: ['confirmar_senha'], message: 'As senhas não conferem' })
    }
  })

export type UserCreateValues = z.infer<typeof userCreateSchema>
