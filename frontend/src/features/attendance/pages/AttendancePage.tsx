import { useState, type FormEvent } from 'react'
import { CalendarCheck } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useClassesInScope, useClassName } from '@/features/classes/hooks'
import { useEnrolledStudents } from '@/features/enrollments/useEnrolledStudents'
import { formatDate, todayLocal } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { Field } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifySuccess } from '@/shared/ui/toast'
import { useAttendanceOn, useSaveRoll } from '../hooks'
import { RollList } from '../components/RollList'
import { buildRoll, rollErrorMessage, type RollEntry } from '../roll'

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

function RollSection({ turmaId, day }: { turmaId: number; day: string }) {
  const className = useClassName(turmaId)
  const enrolled = useEnrolledStudents(turmaId)
  const existing = useAttendanceOn(turmaId, day)
  const save = useSaveRoll()
  const [overrides, setOverrides] = useState<Record<number, boolean>>({})
  const [saveError, setSaveError] = useState<string | null>(null)

  const names = new Map(enrolled.rows.map((row) => [row.matricula.id, row.estudante?.nome ?? '—']))
  const nameOf = (matriculaId: number) => names.get(matriculaId) ?? '—'
  const entries = buildRoll(
    enrolled.rows.map((row) => row.matricula),
    existing.data ?? [],
    day,
  )
  const presenceOf = (entry: RollEntry) => overrides[entry.matricula_id] ?? entry.presente
  const presentes = entries.filter(presenceOf).length
  const faltas = entries.length - presentes
  const anySaved = entries.some((entry) => entry.saved)

  function setAll(presente: boolean) {
    setOverrides(Object.fromEntries(entries.map((entry) => [entry.matricula_id, presente])))
  }

  function handleSave() {
    setSaveError(null)
    save.mutate(
      {
        turma_id: turmaId,
        data: day,
        registros: entries.map((entry) => ({ matricula_id: entry.matricula_id, presente: presenceOf(entry) })),
      },
      {
        onSuccess: () => notifySuccess('Frequência salva'),
        onError: (error) => setSaveError(rollErrorMessage(error, (id) => names.get(id))),
      },
    )
  }

  if (enrolled.isLoading || existing.isPending) {
    return (
      <Panel title="Chamada">
        <PageState status="loading" />
      </Panel>
    )
  }
  if (enrolled.error || existing.isError) {
    return (
      <Panel title="Chamada">
        <PageState status="error" error={enrolled.error ?? existing.error} />
      </Panel>
    )
  }

  return (
    <Panel title="Chamada" caption={`${className} · ${formatDate(day)}`}>
      {entries.length === 0 ? (
        <PageState status="empty" emptyText="Nenhum estudante matriculado nesta data" />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => setAll(true)}>
                Todos presentes
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setAll(false)}>
                Todos falta
              </Button>
            </div>
          </div>
          {saveError && (
            <p role="alert" className="mb-4 rounded-[14px] bg-[rgba(220,38,38,0.1)] px-4 py-3 text-body text-danger">
              {saveError}
            </p>
          )}
          <RollList
            entries={entries}
            nameOf={nameOf}
            presenceOf={presenceOf}
            onChange={(matriculaId, presente) => setOverrides((current) => ({ ...current, [matriculaId]: presente }))}
          />
          <div className="sticky bottom-0 -mx-5 -mb-5 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-b-[22px] border-t border-line bg-glass-strong backdrop-blur-xl px-5 py-3 lg:-mx-6 lg:-mb-6 lg:px-6">
            <Badge variant="default" aria-live="polite">
              {`${plural(presentes, 'presente', 'presentes')} · ${plural(faltas, 'falta', 'faltas')}`}
            </Badge>
            <Button onClick={handleSave} disabled={save.isPending}>
              {anySaved ? 'Atualizar' : 'Salvar'}
            </Button>
          </div>
        </>
      )}
    </Panel>
  )
}

export function AttendancePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const classes = useClassesInScope()
  const turmaParam = searchParams.get('turma') ?? ''
  const dataParam = searchParams.get('data') ?? ''
  const today = todayLocal()

  const [turma, setTurma] = useState(turmaParam)
  const [day, setDay] = useState(dataParam || today)
  const futureDay = day > today
  const canLoad = turma !== '' && day !== '' && !futureDay
  const turmaId = Number(turmaParam)
  const isActive = turmaId > 0 && dataParam !== '' && dataParam <= today

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canLoad) return
    setSearchParams({ turma, data: day })
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Frequência" description="Chamada diária da turma">
        <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
          <div className="w-64 max-w-full">
            <Field label="Turma">
              <select value={turma} onChange={(event) => setTurma(event.target.value)}>
                <option value="">Selecione a turma</option>
                {(classes.data ?? []).map((turmaOption) => (
                  <option key={turmaOption.id} value={String(turmaOption.id)}>
                    {turmaOption.nome}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="w-44">
            <Field label="Data" error={futureDay ? 'A data não pode ser futura' : undefined}>
              <input type="date" value={day} max={today} onChange={(event) => setDay(event.target.value)} />
            </Field>
          </div>
          <Button type="submit" disabled={!canLoad}>
            Carregar
          </Button>
        </form>
      </PageHeader>

      {isActive ? (
        <RollSection key={`${turmaId}-${dataParam}`} turmaId={turmaId} day={dataParam} />
      ) : (
        <Panel>
          <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
            <CalendarCheck size={32} strokeWidth={1.5} className="text-ink-muted opacity-60" aria-hidden="true" />
            <p className="text-body text-ink-muted">Escolha a turma e a data para fazer a chamada</p>
          </div>
        </Panel>
      )}
    </div>
  )
}
