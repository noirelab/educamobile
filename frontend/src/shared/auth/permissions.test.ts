import { describe, expect, it } from 'vitest'
import { access, canWrite, usesPanel, type Access, type Resource, type Role } from './permissions'

const RESOURCES: Resource[] = ['dashboard', 'schools', 'students', 'stops', 'routes', 'users']

const NONE: Record<Resource, Access> = {
  dashboard: 'none',
  schools: 'none',
  students: 'none',
  stops: 'none',
  routes: 'none',
  users: 'none',
}

const expected: Record<Role, Record<Resource, Access>> = {
  admin: {
    dashboard: 'read',
    schools: 'write',
    students: 'write',
    stops: 'write',
    routes: 'write',
    users: 'write',
  },
  gestor: {
    dashboard: 'read',
    schools: 'read',
    students: 'write',
    stops: 'write',
    routes: 'write',
    users: 'write',
  },
  motorista: NONE,
  monitor: NONE,
  responsavel: NONE,
  escola: NONE,
}

const cases = (Object.keys(expected) as Role[]).flatMap((role) =>
  RESOURCES.map((resource) => [role, resource, expected[role][resource]] as const),
)

describe('permissions matrix', () => {
  it('covers all 36 role x resource pairs', () => {
    expect(cases).toHaveLength(36)
  })

  it.each(cases)('%s on %s grants %s', (role, resource, level) => {
    expect(access(role, resource)).toBe(level)
  })

  it.each(cases)('canWrite(%s, %s) is true only for write', (role, resource, level) => {
    expect(canWrite(role, resource)).toBe(level === 'write')
  })

  it('only admin and gestor use the panel', () => {
    expect((Object.keys(expected) as Role[]).filter(usesPanel)).toEqual(['admin', 'gestor'])
  })
})
