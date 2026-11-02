import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { usePager } from './usePager'

describe('usePager', () => {
  it('starts at offset 0 without previous page', () => {
    const { result } = renderHook(() => usePager())
    expect(result.current.offset).toBe(0)
    expect(result.current.hasPrev).toBe(false)
  })

  it('hasNext is true only when rows fill the limit', () => {
    const { result } = renderHook(() => usePager(50))
    expect(result.current.hasNext(new Array(50).fill(0))).toBe(true)
    expect(result.current.hasNext(new Array(49).fill(0))).toBe(false)
  })

  it('next advances offset by limit', () => {
    const { result } = renderHook(() => usePager(50))
    act(() => result.current.next())
    expect(result.current.offset).toBe(50)
    expect(result.current.hasPrev).toBe(true)
  })

  it('prev never goes below 0', () => {
    const { result } = renderHook(() => usePager(50))
    act(() => result.current.prev())
    expect(result.current.offset).toBe(0)
  })

  it('reset returns to first page', () => {
    const { result } = renderHook(() => usePager(50))
    act(() => result.current.next())
    act(() => result.current.next())
    expect(result.current.offset).toBe(100)
    act(() => result.current.reset())
    expect(result.current.offset).toBe(0)
    expect(result.current.hasPrev).toBe(false)
  })
})
