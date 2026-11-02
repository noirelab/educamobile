import { Button } from '@/shared/ui/button'
import type { Pager as PagerState } from '@/shared/ui/usePager'

type PagerProps = {
  pager: PagerState
  rows: unknown[]
}

export function Pager({ pager, rows }: PagerProps) {
  return (
    <div className="flex items-center justify-end gap-2 px-4 py-3">
      <Button variant="secondary" size="sm" onClick={pager.prev} disabled={!pager.hasPrev}>
        Anterior
      </Button>
      <Button variant="secondary" size="sm" onClick={pager.next} disabled={!pager.hasNext(rows)}>
        Próxima
      </Button>
    </div>
  )
}
