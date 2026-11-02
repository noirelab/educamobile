import { describe, expect, it } from 'vitest'
import { addStop, moveStop, removeStop, routeColor, ROUTE_COLORS, sameIds } from './sequence'

describe('sequence helpers', () => {
  it('addStop appends a new id and ignores duplicates', () => {
    expect(addStop([1, 2], 3)).toEqual([1, 2, 3])
    expect(addStop([1, 2], 2)).toEqual([1, 2])
  })

  it('removeStop drops the id and keeps the order', () => {
    expect(removeStop([1, 2, 3], 2)).toEqual([1, 3])
  })

  it('moveStop moves an item to a new index', () => {
    expect(moveStop([1, 2, 3], 0, 2)).toEqual([2, 3, 1])
    expect(moveStop([1, 2, 3], 2, 0)).toEqual([3, 1, 2])
  })

  it('sameIds compares order too', () => {
    expect(sameIds([1, 2], [1, 2])).toBe(true)
    expect(sameIds([1, 2], [2, 1])).toBe(false)
    expect(sameIds([1], [1, 2])).toBe(false)
  })

  it('routeColor is stable and uses only the palette', () => {
    expect(ROUTE_COLORS).toHaveLength(8)
    expect(routeColor(3)).toBe(routeColor(3))
    expect(ROUTE_COLORS).toContain(routeColor(9))
  })
})
