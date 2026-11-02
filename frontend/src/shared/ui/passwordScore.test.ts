import { describe, expect, it } from 'vitest'
import { passwordScore } from './passwordScore'

describe('passwordScore', () => {
  it('scores 0 for short passwords', () => {
    expect(passwordScore('abc')).toBe(0)
  })

  it('scores 1 for length 10 only', () => {
    expect(passwordScore('abcdefghij')).toBe(1)
  })

  it('adds mixed case', () => {
    expect(passwordScore('Abcdefghij')).toBe(2)
  })

  it('adds digit', () => {
    expect(passwordScore('Abcdefghi1')).toBe(3)
  })

  it('adds symbol', () => {
    expect(passwordScore('Abcdefgh1!')).toBe(4)
  })
})
