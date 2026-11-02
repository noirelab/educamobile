import { AlertTriangle, Inbox } from 'lucide-react'
import { errorMessage } from '@/shared/api/errors'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/Skeleton'

type PageStateProps = {
  status: 'loading' | 'empty' | 'error'
  emptyText?: string
  error?: unknown
  onRetry?: () => void
}

export function PageState({ status, emptyText = 'Nenhum registro encontrado', error, onRetry }: PageStateProps) {
  if (status === 'loading') {
    return (
      <div role="status" aria-label="Carregando" className="flex flex-col gap-4 p-4">
        <Skeleton className="h-[18px] w-full" />
        <Skeleton className="h-[18px] w-11/12" />
        <Skeleton className="h-[18px] w-3/4" />
        <Skeleton className="h-[18px] w-1/2" />
      </div>
    )
  }

  if (status === 'empty') {
    return (
      <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
        <Inbox size={32} strokeWidth={1.5} className="text-ink-muted opacity-60" aria-hidden="true" />
        <p className="text-body text-ink-muted">{emptyText}</p>
      </div>
    )
  }

  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <AlertTriangle size={32} strokeWidth={1.5} className="text-danger" aria-hidden="true" />
      <p className="text-body text-danger">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Tentar de novo
        </Button>
      )}
    </div>
  )
}
