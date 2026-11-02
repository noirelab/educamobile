export type Role = 'admin' | 'diretor' | 'coordenador'

export type Resource =
  | 'dashboard'
  | 'poles'
  | 'schools'
  | 'classes'
  | 'teachers'
  | 'students'
  | 'enrollments'
  | 'attendance'
  | 'stops'
  | 'routes'
  | 'users'

export type Access = 'none' | 'read' | 'write'

const matrix: Record<Role, Record<Resource, Access>> = {
  admin: {
    dashboard: 'write',
    poles: 'write',
    schools: 'write',
    classes: 'write',
    teachers: 'write',
    students: 'write',
    enrollments: 'write',
    attendance: 'write',
    stops: 'write',
    routes: 'write',
    users: 'write',
  },
  diretor: {
    dashboard: 'read',
    poles: 'read',
    schools: 'read',
    classes: 'write',
    teachers: 'write',
    students: 'write',
    enrollments: 'write',
    attendance: 'write',
    stops: 'read',
    routes: 'read',
    users: 'none',
  },
  coordenador: {
    dashboard: 'read',
    poles: 'read',
    schools: 'read',
    classes: 'read',
    teachers: 'none',
    students: 'read',
    enrollments: 'none',
    attendance: 'none',
    stops: 'write',
    routes: 'write',
    users: 'none',
  },
}

export function access(role: Role, resource: Resource): Access {
  return matrix[role][resource]
}

export function canWrite(role: Role, resource: Resource): boolean {
  return access(role, resource) === 'write'
}
