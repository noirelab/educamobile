import type { components } from '@/shared/api/schema'

type Turno = components['schemas']['Turno']

export const TURNO_LABEL: Record<Turno, string> = {
  manha: 'Manhã',
  tarde: 'Tarde',
  noite: 'Noite',
  integral: 'Integral',
}

export const TURNO_OPTIONS = Object.keys(TURNO_LABEL) as Turno[]
