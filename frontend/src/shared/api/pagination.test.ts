import { describe, expect, it, vi } from 'vitest'
import { fetchAllPages } from '@/shared/api/pagination'

describe('fetchAllPages', () => {
  it('loads every page until a short page', async () => {
    const page = vi.fn((l: number, o: number) => Promise.resolve(o < 400 ? Array(l).fill(o) : [1]))
    expect((await fetchAllPages(page, 200)).length).toBe(401)
    expect(page).toHaveBeenCalledTimes(3)
  })

  it('uses 200 as default limit', async () => {
    const page = vi.fn(() => Promise.resolve([] as number[]))
    await fetchAllPages(page)
    expect(page).toHaveBeenCalledWith(200, 0)
  })
})
