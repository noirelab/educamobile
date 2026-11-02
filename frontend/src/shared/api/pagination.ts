export async function fetchAllPages<T>(
  page: (limit: number, offset: number) => Promise<T[]>,
  limit = 200,
): Promise<T[]> {
  const all: T[] = []
  let offset = 0
  for (;;) {
    const rows = await page(limit, offset)
    all.push(...rows)
    if (rows.length < limit) return all
    offset += limit
  }
}
