import { afterEach, describe, expect, it, vi } from 'vitest'
import { daysAgoLocal, formatDate, formatMeters, formatPercent, todayLocal } from './format'

describe('formatPercent', () => {
  it('formats a rate as pt-BR percent with one decimal', () => {
    expect(formatPercent(0.164)).toBe('16,4%')
  })

  it('formats zero with one decimal', () => {
    expect(formatPercent(0)).toBe('0,0%')
  })
})

describe('formatMeters', () => {
  it('formats meters with pt-BR thousands separator', () => {
    expect(formatMeters(4493)).toBe('4.493 m')
  })

  it('returns an em dash for null', () => {
    expect(formatMeters(null)).toBe('—')
  })
})

describe('formatDate', () => {
  it('converts YYYY-MM-DD to DD/MM/YYYY without timezone shift', () => {
    expect(formatDate('2026-10-26')).toBe('26/10/2026')
  })
})

describe('local date helpers', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('todayLocal uses local calendar date', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 10, 2, 23, 30))
    expect(todayLocal()).toBe('2026-11-02')
  })

  it('daysAgoLocal subtracts days in local time', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 10, 2, 23, 30))
    expect(daysAgoLocal(30)).toBe('2026-10-03')
  })
})
