import { describe, expect, it } from 'vitest'
import { rateColor } from './heat'

describe('rateColor', () => {
  it('is yellow at zero and red from 40 percent', () => {
    expect(rateColor(0)).toBe('#facc15')
    expect(rateColor(0.4)).toBe('#dc2626')
    expect(rateColor(0.9)).toBe('#dc2626')
  })

  it('interpolates between yellow and red', () => {
    expect(rateColor(0.2)).toBe('#eb791e')
  })
})
