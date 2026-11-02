import { Link } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { GlassPanel } from '@/shared/ui/GlassPanel'

export function ForbiddenPage() {
  return (
    <GlassPanel className="mx-auto flex w-full max-w-[480px] flex-col items-center gap-4 p-8 text-center">
      <Lock size={32} strokeWidth={1.75} aria-hidden="true" className="text-ink-muted" />
      <h1 className="text-section font-semibold text-ink">Sem permissão</h1>
      <p className="text-body text-ink-muted">Você não tem permissão para acessar esta página</p>
      <Button asChild>
        <Link to="/">Voltar ao painel</Link>
      </Button>
    </GlassPanel>
  )
}
