import { cn } from '@/shared/lib/utils'
import { Badge } from '@/shared/ui/badge'
import { Reveal } from '@/shared/ui/Reveal'
import type { RollEntry } from '../roll'
import { PresenceToggle } from './PresenceToggle'

type RollListProps = {
  entries: RollEntry[]
  nameOf: (matriculaId: number) => string
  presenceOf: (entry: RollEntry) => boolean
  onChange: (matriculaId: number, presente: boolean) => void
}

export function RollList({ entries, nameOf, presenceOf, onChange }: RollListProps) {
  return (
    <ul role="list" className="divide-y divide-line">
      {entries.map((entry, index) => {
        const name = nameOf(entry.matricula_id)
        return (
          <li
            key={entry.matricula_id}
            className={cn(
              'relative py-3 pl-3',
              !presenceOf(entry) && 'before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-danger',
            )}
          >
            <Reveal index={index}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="text-body font-medium text-ink">{name}</span>
                  {entry.saved && <Badge variant="default">Já lançado</Badge>}
                </div>
                <PresenceToggle
                  label={`Frequência de ${name}`}
                  presente={presenceOf(entry)}
                  onChange={(presente) => onChange(entry.matricula_id, presente)}
                />
              </div>
            </Reveal>
          </li>
        )
      })}
    </ul>
  )
}
