import { describe, expect, it } from 'vitest'
import { ApiError, errorMessage, toApiError } from '@/shared/api/errors'

describe('toApiError', () => {
  it('maps FastAPI 422 list to field errors', () => {
    const e = toApiError(422, { detail: [{ loc: ['body', 'codigo_inep'], msg: 'String should match pattern' }] })
    expect(e.fieldErrors).toEqual({ codigo_inep: 'String should match pattern' })
  })

  it('keeps string detail', () => {
    expect(toApiError(409, { detail: 'Estudante já tem matrícula ativa' }).detail).toBe('Estudante já tem matrícula ativa')
  })

  it('returns an ApiError instance', () => {
    const e = toApiError(500, undefined)
    expect(e).toBeInstanceOf(ApiError)
    expect(e.status).toBe(500)
    expect(e.fieldErrors).toEqual({})
  })
})

describe('errorMessage', () => {
  const cases: [number, string][] = [
    [0, 'Não foi possível conectar ao servidor'],
    [401, 'Sessão expirada. Entre novamente'],
    [403, 'Você não tem permissão para esta ação'],
    [404, 'Registro não encontrado'],
    [429, 'Muitas tentativas. Tente novamente em 15 minutos'],
    [500, 'Erro inesperado. Tente novamente'],
  ]
  it.each(cases)('status %i', (status, message) => {
    expect(errorMessage(toApiError(status, undefined))).toBe(message)
  })

  it('shows string detail for 409 and 422', () => {
    expect(errorMessage(toApiError(409, { detail: 'Conflito' }))).toBe('Conflito')
    expect(errorMessage(toApiError(422, { detail: 'Inválido' }))).toBe('Inválido')
  })

  it('falls back for non-ApiError values', () => {
    expect(errorMessage(new Error('boom'))).toBe('Erro inesperado. Tente novamente')
  })
})
