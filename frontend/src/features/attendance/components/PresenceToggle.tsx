import { Check, X } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

type PresenceToggleProps = {
  label: string
  presente: boolean
  onChange: (presente: boolean) => void
  disabled?: boolean
}

const OPTIONS: { value: boolean; text: string; selectedClass: string; Icon: typeof Check }[] = [
  { value: true, text: 'Presente', selectedClass: 'bg-success text-white', Icon: Check },
  { value: false, text: 'Falta', selectedClass: 'bg-danger text-white', Icon: X },
]

export function PresenceToggle({ label, presente, onChange, disabled = false }: PresenceToggleProps) {
  return (
    <div role="group" aria-label={label} className="inline-flex shrink-0 overflow-hidden rounded-[14px] border border-line bg-transparent">
      {OPTIONS.map((option) => {
        const selected = option.value === presente
        return (
          <button
            key={option.text}
            type="button"
            aria-pressed={selected}
            disabled={disabled}
            onClick={() => {
              if (!selected) onChange(option.value)
            }}
            className={cn(
              'focus-ring h-11 min-w-[104px] px-4 text-button transition-[background-color,color,transform] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)] active:scale-[.97] disabled:opacity-50',
              selected ? option.selectedClass : 'text-ink-muted hover:bg-[rgba(15,30,51,0.06)]',
            )}
          >
            <span className="inline-flex items-center justify-center gap-1.5">
              {selected && <option.Icon size={16} strokeWidth={2.5} aria-hidden="true" />}
              {option.text}
            </span>
          </button>
        )
      })}
    </div>
  )
}
