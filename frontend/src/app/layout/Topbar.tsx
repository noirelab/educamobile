import { Link, useLocation } from 'react-router-dom'
import { LogOut, Menu } from 'lucide-react'
import { breadcrumbFor, ROLE_LABELS } from '@/app/nav'
import { useAuth } from '@/shared/auth/useAuth'
import { Button } from '@/shared/ui/button'
import { GlassPanel } from '@/shared/ui/GlassPanel'
import { useLiquidGlass } from '@/shared/ui/useLiquidGlass'

type TopbarProps = { onOpenMenu: () => void }

export function Topbar({ onOpenMenu }: TopbarProps) {
  const { user, role, logout } = useAuth()
  const location = useLocation()
  const chipRef = useLiquidGlass<HTMLAnchorElement>(true, 999, true)

  if (!user || !role) return null

  const crumbs = breadcrumbFor(location.pathname)

  return (
    <GlassPanel as="header" className="flex h-16 items-center justify-between gap-3 px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Button variant="ghost" size="icon" className="shrink-0 lg:hidden" aria-label="Abrir menu" onClick={onOpenMenu}>
          <Menu strokeWidth={1.75} />
        </Button>
        {crumbs.length > 0 && (
          <nav aria-label="Trilha de navegação" className="min-w-0">
            <ol className="flex min-w-0 items-center gap-2 text-label text-ink-muted">
              {crumbs.map((crumb, index) => (
                <li
                  key={`${crumb}-${index}`}
                  className="flex min-w-0 items-center gap-2"
                  aria-current={index === crumbs.length - 1 ? 'page' : undefined}
                >
                  {index > 0 && <span aria-hidden="true">/</span>}
                  <span className={index === crumbs.length - 1 ? 'truncate font-semibold text-ink' : 'truncate'}>
                    {crumb}
                  </span>
                </li>
              ))}
            </ol>
          </nav>
        )}
      </div>
      <div className="flex min-w-0 shrink items-center gap-3 sm:shrink-0">
        <Link
          ref={chipRef}
          to="/profile"
          aria-label={`Perfil de ${user.nome}`}
          className="glass glass-strong liquid flex min-w-0 shrink-0 items-center gap-2.5 rounded-full px-2 py-1.5 text-label sm:px-3.5 sm:py-2"
        >
          <span
            aria-hidden="true"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-label font-semibold text-accent sm:hidden"
          >
            {user.nome.charAt(0).toUpperCase()}
          </span>
          <span className="hidden truncate text-[14px] font-semibold text-ink sm:inline">{user.nome}</span>
          <span className="hidden text-caption text-ink-muted md:inline">{ROLE_LABELS[role]}</span>
        </Link>
        <Button variant="ghost" className="shrink-0" aria-label="Sair" onClick={() => logout()}>
          <LogOut strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden sm:inline">Sair</span>
        </Button>
      </div>
    </GlassPanel>
  )
}
