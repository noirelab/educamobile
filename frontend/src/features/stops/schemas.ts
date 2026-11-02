export const MAX_RADIUS_M = 50000

export type NearbyValues = { latitude: number; longitude: number; raio_m: number }
export type NearbyErrors = Partial<Record<'latitude' | 'longitude' | 'raio_m', string>>

export type NearbyRaw = { latitude: string; longitude: string; raio: string }

export type NearbyParseResult =
  | { values: NearbyValues; errors: null }
  | { values: null; errors: NearbyErrors }

function toNumber(raw: string): number {
  if (raw.trim() === '') return Number.NaN
  return Number(raw.replace(',', '.'))
}

export function parseNearbyForm(raw: NearbyRaw): NearbyParseResult {
  const latitude = toNumber(raw.latitude)
  const longitude = toNumber(raw.longitude)
  const raio_m = toNumber(raw.raio)
  const errors: NearbyErrors = {}

  if (!Number.isFinite(latitude) || Math.abs(latitude) > 90) errors.latitude = 'Latitude entre -90 e 90'
  if (!Number.isFinite(longitude) || Math.abs(longitude) > 180) errors.longitude = 'Longitude entre -180 e 180'
  if (!Number.isFinite(raio_m) || raio_m <= 0) errors.raio_m = 'Informe um raio maior que zero'
  else if (raio_m > MAX_RADIUS_M) errors.raio_m = 'Raio máximo de 50 km'

  if (Object.keys(errors).length > 0) return { values: null, errors }
  return { values: { latitude, longitude, raio_m }, errors: null }
}

export function parseStopName(raw: string): { nome: string; error: string | null } {
  const nome = raw.trim()
  return nome === '' ? { nome, error: 'Informe o nome' } : { nome, error: null }
}
