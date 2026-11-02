import type { ReactNode } from 'react'
import { ForbiddenPage } from '@/app/pages/ForbiddenPage'
import { access, type Resource } from './permissions'
import { useAuth } from './useAuth'

type Props = {
  resource: Resource
  level: 'read' | 'write'
  children: ReactNode
}

export function RequireAccess({ resource, level, children }: Props) {
  const { role } = useAuth()

  if (!role) return null

  const granted = access(role, resource)
  const allowed = level === 'read' ? granted !== 'none' : granted === 'write'

  if (!allowed) return <ForbiddenPage />

  return <>{children}</>
}
