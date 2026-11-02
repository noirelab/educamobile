import { NavLink } from 'react-router-dom'
import { useAuth } from '@/shared/auth/useAuth'
import { cn } from '@/shared/lib/utils'
import { GlassPanel } from '@/shared/ui/GlassPanel'
import { ROLE_LABELS, visibleNav } from '../nav'

type NavListProps = { onNavigate?: () => void }

export function NavList({ onNavigate }: NavListProps) {
  const { role } = useAuth()

  if (!role) return null

  return (
    <nav aria-label="Menu principal">
      <ul className="flex flex-col gap-1">
        {visibleNav(role).map((item) => {
          const Icon = item.icon
          return (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === '/'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'group flex h-10 items-center gap-3 rounded-[12px] px-3 text-label text-[14px] font-medium transition-[transform,background-color,color,box-shadow] duration-[250ms] ease-[cubic-bezier(0.22,1,0.36,1)] hover:translate-x-[3px] hover:bg-white/10',
                    isActive
                      ? 'bg-white/20 text-on-sidebar shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] [&_svg]:text-[#5eead4]'
                      : 'text-on-sidebar/80',
                  )
                }
              >
                <Icon size={18} strokeWidth={1.75} aria-hidden="true" className="shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export function SidebarUser() {
  const { user, role } = useAuth()

  if (!user || !role) return null

  return (
    <div className="flex items-center gap-3 border-t border-white/15 pt-4">
      <span
        aria-hidden="true"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/15 text-label font-semibold text-on-sidebar"
      >
        {user.nome.charAt(0).toUpperCase()}
      </span>
      <div className="min-w-0">
        <p className="truncate text-label text-on-sidebar">Logado como {user.nome}</p>
        <p className="truncate text-caption text-on-sidebar/70">Perfil: {ROLE_LABELS[role]}</p>
      </div>
    </div>
  )
}

export function SidebarBody({ onNavigate }: NavListProps) {
  return (
    <div className="flex h-full flex-col gap-6">
      <div className="px-1">
        <p className="text-[18px] font-bold leading-6 text-on-sidebar">EducaMobile</p>
        <p className="text-caption text-on-sidebar/70">Secretaria de Educação</p>
      </div>
      <NavList onNavigate={onNavigate} />
      <div className="mt-auto">
        <SidebarUser />
      </div>
    </div>
  )
}

export function Sidebar() {
  return (
    <GlassPanel
      as="aside"
      className="sticky top-5 hidden h-[calc(100vh-2.5rem)] flex-col p-5 text-on-sidebar lg:flex"
      style={{ background: 'var(--sidebar-glass)' }}
    >
      <SidebarBody />
    </GlassPanel>
  )
}
