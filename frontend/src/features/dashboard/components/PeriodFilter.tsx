import { useEffect, useState } from 'react'
import { todayLocal } from '@/shared/lib/format'
import { Field } from '@/shared/ui/Field'
import { usePeriod, type Period } from '../hooks'

export function PeriodFilter() {
  const period = usePeriod()
  const [draft, setDraft] = useState<Period>({ data_inicio: period.data_inicio, data_fim: period.data_fim })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDraft({ data_inicio: period.data_inicio, data_fim: period.data_fim })
    setError(null)
  }, [period.data_inicio, period.data_fim])

  function handleChange(field: keyof Period, value: string) {
    const next = { ...draft, [field]: value }
    setDraft(next)

    if (value > todayLocal()) {
      setError('A data não pode ser futura')
      return
    }
    if (next.data_inicio > next.data_fim) {
      setError('A data inicial não pode ser posterior à final')
      return
    }

    setError(null)
    period.set(next)
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-44">
        <Field label="De">
          <input
            type="date"
            value={draft.data_inicio}
            max={todayLocal()}
            onChange={(event) => handleChange('data_inicio', event.target.value)}
          />
        </Field>
      </div>
      <div className="w-44">
        <Field label="Até">
          <input
            type="date"
            value={draft.data_fim}
            max={todayLocal()}
            onChange={(event) => handleChange('data_fim', event.target.value)}
          />
        </Field>
      </div>
      {error && (
        <p role="alert" className="basis-full text-caption text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
