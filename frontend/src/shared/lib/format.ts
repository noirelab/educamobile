const pt = 'pt-BR'

const percentFormatter = new Intl.NumberFormat(pt, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const metersFormatter = new Intl.NumberFormat(pt, {
  maximumFractionDigits: 0,
})

const pad = (value: number) => String(value).padStart(2, '0')

const toIsoLocal = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

export function formatPercent(rate: number): string {
  return `${percentFormatter.format(rate * 100)}%`
}

export function formatMeters(m: number | null): string {
  if (m === null) return '—'
  return `${metersFormatter.format(m)} m`
}

export function formatDate(iso: string): string {
  const [year, month, day] = iso.split('-')
  return `${day}/${month}/${year}`
}

export function todayLocal(): string {
  return toIsoLocal(new Date())
}

export function daysAgoLocal(n: number): string {
  const date = new Date()
  date.setDate(date.getDate() - n)
  return toIsoLocal(date)
}
