import { describe, expect, it } from 'vitest'
import { todayLocal } from '@/shared/lib/format'
import { studentSchema } from './schemas'

const BASE = {
  nome: 'Lucas Ferreira',
  data_nascimento: '2015-01-01',
  escola_id: '1',
  turno: 'manha',
  parada_id: '',
  observacoes_cuidado: '',
}

describe('studentSchema', () => {
  it('accepts the minimum data for the transport', () => {
    expect(studentSchema.safeParse(BASE).success).toBe(true)
  })

  it('rejects a birth date equal to today', () => {
    const result = studentSchema.safeParse({ ...BASE, data_nascimento: todayLocal() })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('A data de nascimento deve estar no passado')
  })

  it('requires the school', () => {
    const result = studentSchema.safeParse({ ...BASE, escola_id: '' })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('Informe a escola')
  })

  it('rejects an unknown shift', () => {
    expect(studentSchema.safeParse({ ...BASE, turno: 'madrugada' }).success).toBe(false)
  })

  it('limits the care notes to 1000 characters', () => {
    expect(studentSchema.safeParse({ ...BASE, observacoes_cuidado: 'x'.repeat(1001) }).success).toBe(false)
  })
})
