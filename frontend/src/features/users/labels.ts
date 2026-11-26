import type { components } from '@/shared/api/schema'

type Perfil = components['schemas']['Perfil']

export const PERFIL_LABEL: Record<Perfil, string> = {
  admin: 'Administrador',
  gestor: 'Gestor de transporte',
  motorista: 'Motorista',
  monitor: 'Monitor',
  responsavel: 'Responsável',
}

// Responsável entra por convite, não por cadastro direto.
export const PERFIS_CRIAVEIS: Perfil[] = ['admin', 'gestor', 'motorista', 'monitor']
// O gestor só cria motorista e monitor.
export const PERFIS_CRIAVEIS_PELO_GESTOR: Perfil[] = ['motorista', 'monitor']
