import { describe, expect, it } from 'vitest'
import { classSchema } from './schemas'

const VALID = {
  escola_id: '1',
  nome: '6A',
  serie: '6º ano',
  turno: 'manha',
  ano_letivo: '2026',
}

describe('classSchema', () => {
  it('accepts a complete class', () => {
    expect(classSchema.safeParse(VALID).success).toBe(true)
  })

  it('accepts the 2000 and 2100 bounds', () => {
    expect(classSchema.safeParse({ ...VALID, ano_letivo: '2000' }).success).toBe(true)
    expect(classSchema.safeParse({ ...VALID, ano_letivo: '2100' }).success).toBe(true)
  })

  it('rejects ano_letivo 1999', () => {
    const result = classSchema.safeParse({ ...VALID, ano_letivo: '1999' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Ano letivo entre 2000 e 2100')
  })

  it('rejects ano_letivo 2101 and non numeric values', () => {
    expect(classSchema.safeParse({ ...VALID, ano_letivo: '2101' }).success).toBe(false)
    expect(classSchema.safeParse({ ...VALID, ano_letivo: '20x6' }).success).toBe(false)
  })

  it('rejects an empty nome', () => {
    const result = classSchema.safeParse({ ...VALID, nome: '   ' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Informe o nome')
  })

  it('rejects an empty serie', () => {
    const result = classSchema.safeParse({ ...VALID, serie: '' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Informe a série')
  })

  it('rejects a turno outside the allowed values', () => {
    expect(classSchema.safeParse({ ...VALID, turno: 'madrugada' }).success).toBe(false)
  })
})
