import { describe, expect, it } from 'vitest'
import { poleSchema } from './schemas'

describe('poleSchema', () => {
  it('rejects an empty nome', () => {
    const result = poleSchema.safeParse({ nome: '' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Informe o nome')
  })

  it('rejects a blank nome', () => {
    expect(poleSchema.safeParse({ nome: '   ' }).success).toBe(false)
  })

  it('accepts a filled nome', () => {
    expect(poleSchema.safeParse({ nome: 'Polo Centro' }).success).toBe(true)
  })
})
