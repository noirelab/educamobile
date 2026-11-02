import {
  Backpack,
  CalendarCheck,
  GraduationCap,
  Hexagon,
  LayoutDashboard,
  MapPin,
  Route,
  School,
  Users,
  UserRoundPlus,
  type LucideIcon,
} from 'lucide-react'
import { access, type Resource, type Role } from '@/shared/auth/permissions'

export type NavItem = { label: string; path: string; resource: Resource; icon: LucideIcon }

export const NAV_ITEMS: NavItem[] = [
  { label: 'Painel', path: '/', resource: 'dashboard', icon: LayoutDashboard },
  { label: 'Polos', path: '/poles', resource: 'poles', icon: Hexagon },
  { label: 'Escolas', path: '/schools', resource: 'schools', icon: School },
  { label: 'Turmas', path: '/classes', resource: 'classes', icon: Users },
  { label: 'Professores', path: '/teachers', resource: 'teachers', icon: GraduationCap },
  { label: 'Estudantes', path: '/students', resource: 'students', icon: Backpack },
  { label: 'Frequência', path: '/attendance', resource: 'attendance', icon: CalendarCheck },
  { label: 'Paradas', path: '/stops', resource: 'stops', icon: MapPin },
  { label: 'Rotas', path: '/routes', resource: 'routes', icon: Route },
  { label: 'Usuários', path: '/users', resource: 'users', icon: UserRoundPlus },
]

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrador',
  diretor: 'Diretor',
  coordenador: 'Coordenador de logística',
}

export function visibleNav(role: Role): typeof NAV_ITEMS {
  return NAV_ITEMS.filter((item) => access(role, item.resource) !== 'none')
}

const SUB_PAGE_LABELS: Record<string, string> = {
  new: 'Novo',
  edit: 'Editar',
}

export function breadcrumbFor(pathname: string): string[] {
  if (pathname === '/profile') return ['Perfil']

  const section = NAV_ITEMS.find((item) =>
    item.path === '/' ? pathname === '/' : pathname === item.path || pathname.startsWith(`${item.path}/`),
  )
  if (!section) return []

  const rest = pathname.slice(section.path.length).split('/').filter(Boolean)
  const crumbs = [section.label]
  rest.forEach((segment) => {
    crumbs.push(SUB_PAGE_LABELS[segment] ?? 'Detalhe')
  })
  return crumbs
}
