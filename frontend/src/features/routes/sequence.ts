export const ROUTE_COLORS: string[] = [
  '#0f766e',
  '#2563eb',
  '#7c3aed',
  '#c026d3',
  '#0891b2',
  '#15803d',
  '#4338ca',
  '#57534e',
]

export function addStop(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids : [...ids, id]
}

export function removeStop(ids: number[], id: number): number[] {
  return ids.filter((current) => current !== id)
}

export function moveStop(ids: number[], from: number, to: number): number[] {
  const next = [...ids]
  const [item] = next.splice(from, 1)
  if (item === undefined) return ids
  next.splice(to, 0, item)
  return next
}

export function sameIds(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((id, index) => id === b[index])
}

export function routeColor(routeId: number): string {
  return ROUTE_COLORS[Math.abs(routeId) % ROUTE_COLORS.length] ?? ROUTE_COLORS[0]
}
