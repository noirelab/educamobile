import { z } from 'zod'
import { PERFIS_CRIAVEIS } from './labels'

export const userCreateSchema = z
  .object({
    nome: z.string().trim().min(1, 'Informe o nome'),
    email: z.string().trim().email('E-mail inválido'),
    perfil: z.string().refine((value) => (PERFIS_CRIAVEIS as string[]).includes(value), 'Informe o perfil'),
    senha: z.string().min(10, 'Mínimo de 10 caracteres').max(128, 'Máximo de 128 caracteres'),
    confirmar_senha: z.string(),
  })
  .superRefine((values, ctx) => {
    if (values.senha !== values.confirmar_senha) {
      ctx.addIssue({ code: 'custom', path: ['confirmar_senha'], message: 'As senhas não conferem' })
    }
  })

export type UserCreateValues = z.infer<typeof userCreateSchema>

export const passwordChangeSchema = z
  .object({
    senha_atual: z.string().min(1, 'Informe a senha atual'),
    senha_nova: z.string().min(10, 'Mínimo de 10 caracteres').max(128, 'Máximo de 128 caracteres'),
    confirmar: z.string(),
  })
  .superRefine((values, ctx) => {
    if (values.senha_nova !== values.confirmar) {
      ctx.addIssue({ code: 'custom', path: ['confirmar'], message: 'As senhas não conferem' })
    }
    if (values.senha_nova === values.senha_atual) {
      ctx.addIssue({ code: 'custom', path: ['senha_nova'], message: 'A senha nova precisa ser diferente da atual' })
    }
  })

export type PasswordChangeValues = z.infer<typeof passwordChangeSchema>
