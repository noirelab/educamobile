import { describe, expect, it } from 'vitest'
import { buildSpecularMap } from './liquidMap'
import { chooseBezel, chooseRadius, shouldBuildMap } from './useLiquidGlass'

describe('liquid sizing', () => {
  it('caps bezel at 24 and scales for small elements', () => {
    expect(chooseBezel(400, 300)).toBe(24)
    expect(chooseBezel(60, 40)).toBe(10)
  })

  it('clamps radius to half the smallest side', () => {
    expect(chooseRadius(40, 40, 22)).toBe(20)
    expect(chooseRadius(300, 200, 22)).toBe(22)
  })

  it('skips huge or tiny elements', () => {
    expect(shouldBuildMap(1601, 400)).toBe(false)
    expect(shouldBuildMap(400, 1201)).toBe(false)
    expect(shouldBuildMap(8, 8)).toBe(false)
    expect(shouldBuildMap(400, 300)).toBe(true)
  })
})

describe('buildSpecularMap', () => {
  const w = 200
  const h = 120
  const alphaAt = (d: Uint8ClampedArray, x: number, y: number) => d[(y * w + x) * 4 + 3]

  it('is transparent in the flat interior', () => {
    const d = buildSpecularMap(w, h, 22, 24)
    expect(alphaAt(d, 100, 60)).toBe(0)
  })

  it('is brighter on the edge facing -60 degrees than the opposite edge', () => {
    const d = buildSpecularMap(w, h, 22, 24)
    const lit = alphaAt(d, 170, 0)
    const dark = alphaAt(d, 30, h - 1)
    expect(lit).toBeGreaterThan(150)
    expect(lit).toBeGreaterThan(dark)
  })
})
