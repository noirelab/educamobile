import { useState } from 'react'

export function usePager(pageSize = 50) {
  const [offset, setOffset] = useState(0)

  return {
    offset,
    limit: pageSize,
    next: () => setOffset((current) => current + pageSize),
    reset: () => setOffset(0),
    prev: () => setOffset((current) => Math.max(0, current - pageSize)),
    hasPrev: offset > 0,
    hasNext: (rows: unknown[]) => rows.length === pageSize,
  }
}

export type Pager = ReturnType<typeof usePager>
