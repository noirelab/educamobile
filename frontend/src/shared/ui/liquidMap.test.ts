import { describe, expect, it } from 'vitest'
import { buildDisplacementMap } from './liquidMap'

describe('buildDisplacementMap', () => {
  it('is neutral in the flat interior', () => {
    const d = buildDisplacementMap(100, 60, 20, 16)
    const i = (30 * 100 + 50) * 4
    expect([d[i], d[i + 1], d[i + 2], d[i + 3]]).toEqual([128, 128, 128, 255])
  })

  it('displaces near the left edge along x', () => {
    const d = buildDisplacementMap(100, 60, 20, 16)
    const i = (30 * 100 + 2) * 4
    expect(d[i]).not.toBe(128)
    expect(d[i + 1]).toBe(128)
  })
})
