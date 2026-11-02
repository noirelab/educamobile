import { describe, expect, it } from 'vitest'
import { todayLocal } from '@/shared/lib/format'
import { buildStudentSchema } from './schemas'

const BASE = {
  nome: 'Lucas Ferreira',
  data_nascimento: '2015-01-01',
  nome_responsavel: '',
  localizacao: null,
  turma_id: '',
  data_inicio: '',
  parada_id: '',
}

const CREATE_ADMIN = buildStudentSchema({ isCreate: true, isDiretor: false })
const CREATE_DIRETOR = buildStudentSchema({ isCreate: true, isDiretor: true })
const EDIT = buildStudentSchema({ isCreate: false, isDiretor: false })

describe('buildStudentSchema', () => {
  it('rejects a birth date equal to today', () => {
    const result = EDIT.safeParse({ ...BASE, data_nascimento: todayLocal() })

    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe('A data de nascimento deve estar no passado')
  })

  it('accepts a past birth date', () => {
    expect(EDIT.safeParse(BASE).success).toBe(true)
  })

  it('requires turma and data de início for diretor on create', () => {
    const result = CREATE_DIRETOR.safeParse(BASE)

    expect(result.success).toBe(false)
    const messages = result.error?.issues.map((issue) => issue.message) ?? []
    expect(messages).toContain('Informe a turma e a data de início')
  })

  it('accepts diretor create with a complete matrícula', () => {
    const result = CREATE_DIRETOR.safeParse({ ...BASE, turma_id: '3', data_inicio: '2026-02-03' })

    expect(result.success).toBe(true)
  })

  it('accepts admin create without matrícula', () => {
    expect(CREATE_ADMIN.safeParse(BASE).success).toBe(true)
  })

  it('requires data de início when admin picks a turma', () => {
    const result = CREATE_ADMIN.safeParse({ ...BASE, turma_id: '3' })

    expect(result.success).toBe(false)
    expect(result.error?.issues.map((issue) => issue.message)).toContain('Informe a data de início')
  })

  it('ignores matrícula fields on edit', () => {
    expect(EDIT.safeParse({ ...BASE, turma_id: '', data_inicio: '' }).success).toBe(true)
  })
})
