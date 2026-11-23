// Perfis da API. Só admin e gestor usam o painel; motorista, monitor e responsável
// acessam o que um vínculo libera (viagem escalada, filho) e não veem telas de cadastro.
export type Role = 'admin' | 'gestor' | 'motorista' | 'monitor' | 'responsavel'

export type Resource = 'dashboard' | 'schools' | 'students' | 'stops' | 'routes' | 'users'

export type Access = 'none' | 'read' | 'write'

const FULL: Record<Resource, Access> = {
  dashboard: 'read',
  schools: 'write',
  students: 'write',
  stops: 'write',
  routes: 'write',
  users: 'write',
}

const NONE: Record<Resource, Access> = {
  dashboard: 'none',
  schools: 'none',
  students: 'none',
  stops: 'none',
  routes: 'none',
  users: 'none',
}

const matrix: Record<Role, Record<Resource, Access>> = {
  admin: FULL,
  // O gestor não cria escolas nem remove estudantes; isso segue com o administrador na API.
  gestor: { ...FULL, schools: 'read' },
  motorista: NONE,
  monitor: NONE,
  responsavel: NONE,
}

export function access(role: Role, resource: Resource): Access {
  return matrix[role][resource]
}

export function canWrite(role: Role, resource: Resource): boolean {
  return access(role, resource) === 'write'
}

export function usesPanel(role: Role): boolean {
  return role === 'admin' || role === 'gestor'
}
