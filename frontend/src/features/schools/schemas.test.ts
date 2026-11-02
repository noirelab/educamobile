import { describe, expect, it } from 'vitest'
import { schoolSchema } from './schemas'

const VALID = {
  nome: 'EMEF Centro',
  codigo_inep: '',
  endereco: '',
  polo_id: '',
  localizacao: { latitude: -25.43, longitude: -49.27 },
}

describe('schoolSchema', () => {
  it('accepts an empty codigo_inep', () => {
    expect(schoolSchema.safeParse(VALID).success).toBe(true)
  })

  it('accepts exactly 8 digits in codigo_inep', () => {
    expect(schoolSchema.safeParse({ ...VALID, codigo_inep: '41000011' }).success).toBe(true)
  })

  it('rejects a codigo_inep that is not 8 digits', () => {
    const result = schoolSchema.safeParse({ ...VALID, codigo_inep: '4100001' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('O código INEP tem 8 dígitos')
  })

  it('rejects an empty nome', () => {
    const result = schoolSchema.safeParse({ ...VALID, nome: '   ' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Informe o nome')
  })

  it('requires localizacao', () => {
    const result = schoolSchema.safeParse({ ...VALID, localizacao: null })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Marque a localização no mapa')
  })
})
