import { cn } from '@/shared/lib/utils'
import { passwordScore, type PasswordScore } from '@/shared/ui/passwordScore'

const labels: Record<Exclude<PasswordScore, 0>, string> = {
  1: 'Fraca',
  2: 'Razoável',
  3: 'Boa',
  4: 'Forte',
}

const barColors: Record<Exclude<PasswordScore, 0>, string> = {
  1: 'bg-danger',
  2: 'bg-warning',
  3: 'bg-accent',
  4: 'bg-success',
}

const MIN_LENGTH = 10
const BARS = [1, 2, 3, 4] as const

type PasswordStrengthProps = {
  value: string
}

export function PasswordStrength({ value }: PasswordStrengthProps) {
  const score = passwordScore(value)
  const text = value.length < MIN_LENGTH ? 'Mínimo de 10 caracteres' : labels[score as Exclude<PasswordScore, 0>] ?? ''

  return (
    <div>
      <div aria-hidden="true" className="mt-2 flex gap-1.5">
        {BARS.map((bar) => {
          const active = bar <= score
          return (
            <span
              key={bar}
              className={cn(
                'h-1.5 flex-1 rounded-md bg-white/45 transition-[background-color,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]',
                active && barColors[bar as Exclude<PasswordScore, 0>],
                active && 'scale-y-[1.3]',
              )}
            />
          )
        })}
      </div>
      <p aria-live="polite" className="mt-1.5 min-h-[16px] text-caption text-ink-muted">
        {text}
      </p>
    </div>
  )
}
