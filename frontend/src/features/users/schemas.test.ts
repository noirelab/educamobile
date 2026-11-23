import { describe, expect, it } from 'vitest'
import { userCreateSchema } from './schemas'

const base = {
  nome: 'Ana Souza',
  email: 'ana@educa.test',
  perfil: 'admin',
  senha: 'Senha-forte-123',
  confirmar_senha: 'Senha-forte-123',
}

describe('userCreateSchema', () => {
  it('accepts a valid admin', () => {
    expect(userCreateSchema.safeParse(base).success).toBe(true)
  })

  it('rejects a password under 10 characters', () => {
    const result = userCreateSchema.safeParse({ ...base, senha: 'curta', confirmar_senha: 'curta' })
    expect(result.success).toBe(false)
    expect(result.error?.issues.map((i) => i.message)).toContain('Mínimo de 10 caracteres')
  })

  it('rejects a password over 128 characters', () => {
    const senha = 'a'.repeat(129)
    const result = userCreateSchema.safeParse({ ...base, senha, confirmar_senha: senha })
    expect(result.success).toBe(false)
    expect(result.error?.issues.map((i) => i.message)).toContain('Máximo de 128 caracteres')
  })

  it('accepts a 128 character password', () => {
    const senha = 'a'.repeat(128)
    expect(userCreateSchema.safeParse({ ...base, senha, confirmar_senha: senha }).success).toBe(true)
  })

  it('rejects mismatched confirmation', () => {
    const result = userCreateSchema.safeParse({ ...base, confirmar_senha: 'Outra-senha-123' })
    expect(result.success).toBe(false)
    expect(result.error?.issues.map((i) => i.message)).toContain('As senhas não conferem')
  })

  it('rejects an unknown perfil', () => {
    const result = userCreateSchema.safeParse({ ...base, perfil: '' })
    expect(result.success).toBe(false)
    expect(result.error?.issues.map((i) => i.message)).toContain('Informe o perfil')
  })
})
