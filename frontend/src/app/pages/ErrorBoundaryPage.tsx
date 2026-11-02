import { AlertTriangle } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { GlassPanel } from '@/shared/ui/GlassPanel'

export function ErrorBoundaryPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <GlassPanel strong className="flex w-full max-w-[480px] flex-col items-center gap-4 p-8 text-center">
        <AlertTriangle size={32} strokeWidth={1.75} aria-hidden="true" className="text-danger" />
        <h1 className="text-section font-semibold text-ink">Algo deu errado</h1>
        <p className="text-body text-ink-muted">Recarregue a página para tentar novamente</p>
        <Button onClick={() => window.location.reload()}>Tentar de novo</Button>
      </GlassPanel>
    </div>
  )
}
