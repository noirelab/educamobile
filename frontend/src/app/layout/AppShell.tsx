import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/shared/ui/sheet'
import { Sidebar, SidebarBody } from './Sidebar'
import { Topbar } from './Topbar'

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="min-h-screen p-5 lg:grid lg:grid-cols-[248px_minmax(0,1fr)] lg:gap-5">
      <Sidebar />
      <div className="flex min-w-0 flex-col gap-5">
        <Topbar onOpenMenu={() => setMenuOpen(true)} />
        <main className="mx-0 flex w-full max-w-[1360px] flex-1 flex-col gap-5">
          <div key={location.pathname} className="page-enter flex flex-col gap-5">
            <Outlet />
          </div>
        </main>
      </div>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent
          side="left"
          className="w-[260px] border-0 p-5 text-on-sidebar sm:max-w-[260px]"
          style={{ background: 'var(--sidebar-glass)' }}
        >
          <SheetTitle className="sr-only">EducaMobile</SheetTitle>
          <SheetDescription className="sr-only">Navegação principal</SheetDescription>
          <div className="mt-8 h-[calc(100%-2rem)]">
            <SidebarBody onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
