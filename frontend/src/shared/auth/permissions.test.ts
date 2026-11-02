import { describe, expect, it } from 'vitest'
import { access, canWrite, type Access, type Resource, type Role } from './permissions'

const RESOURCES: Resource[] = [
  'dashboard',
  'poles',
  'schools',
  'classes',
  'teachers',
  'students',
  'enrollments',
  'attendance',
  'stops',
  'routes',
  'users',
]

const expected: Record<Role, Record<Resource, Access>> = {
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

const cases = (Object.keys(expected) as Role[]).flatMap((role) =>
  RESOURCES.map((resource) => [role, resource, expected[role][resource]] as const),
)

describe('permissions matrix', () => {
  it('covers all 33 role x resource pairs', () => {
    expect(cases).toHaveLength(33)
  })

  it.each(cases)('%s on %s grants %s', (role, resource, level) => {
    expect(access(role, resource)).toBe(level)
  })

  it.each(cases)('canWrite(%s, %s) is true only for write', (role, resource, level) => {
    expect(canWrite(role, resource)).toBe(level === 'write')
  })
})
