import type { components } from '@/shared/api/schema'

type Perfil = components['schemas']['Perfil']

export const PERFIL_LABEL: Record<Perfil, string> = {
  admin: 'Administrador',
  diretor: 'Diretor',
  coordenador: 'Coordenador de logística',
}
