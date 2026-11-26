import type { components } from '@/shared/api/schema'

type Perfil = components['schemas']['Perfil']

export const PERFIL_LABEL: Record<Perfil, string> = {
  admin: 'Administrador',
  gestor: 'Gestor de transporte',
  motorista: 'Motorista',
  monitor: 'Monitor',
  responsavel: 'Responsável',
  escola: 'Equipe da escola',
}

// Responsável entra por convite, não por cadastro direto.
export const PERFIS_CRIAVEIS: Perfil[] = ['admin', 'gestor', 'motorista', 'monitor']
// Novo na API: o gestor também cria o perfil 'escola', que exige `escola_id` no POST /usuarios.
// Ele entra nestas listas quando o formulário ganhar o seletor de escola.
// O gestor só cria motorista e monitor.
export const PERFIS_CRIAVEIS_PELO_GESTOR: Perfil[] = ['motorista', 'monitor']
