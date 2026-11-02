import { useState } from 'react'
import { useClassName } from '@/features/classes/hooks'
import { useAuth } from '@/shared/auth/useAuth'
import { canWrite } from '@/shared/auth/permissions'
import { daysAgoLocal, formatDate, todayLocal } from '@/shared/lib/format'
import { Badge } from '@/shared/ui/badge'
import { DataTable } from '@/shared/ui/DataTable'
import { Field } from '@/shared/ui/Field'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import type { components } from '@/shared/api/schema'
import { useSaveAttendance, useStudentAttendance, useStudentEnrollments, type Period } from '../hooks'
import { PresenceToggle } from './PresenceToggle'

type FrequenciaLer = components['schemas']['FrequenciaLer']

function plural(count: number, singular: string, pluralForm: string): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

function ClassNameCell({ turmaId }: { turmaId: number | undefined }) {
  const name = useClassName(turmaId ?? 0)
  return turmaId === undefined ? '—' : name
}

export function StudentAttendance({ studentId }: { studentId: number }) {
  const { role } = useAuth()
  const writable = role !== null && canWrite(role, 'attendance')
  const today = todayLocal()
  const [period, setPeriod] = useState<Period>({ data_inicio: daysAgoLocal(30), data_fim: today })
  const [draft, setDraft] = useState<Period>(period)
  const [periodError, setPeriodError] = useState<string | null>(null)
  const attendance = useStudentAttendance(studentId, period)
  const enrollments = useStudentEnrollments(studentId)
  const save = useSaveAttendance()

  function handleChange(field: keyof Period, value: string) {
    const next = { ...draft, [field]: value }
    setDraft(next)
    if (value > today) {
      setPeriodError('A data não pode ser futura')
      return
    }
    if (next.data_inicio > next.data_fim) {
      setPeriodError('A data inicial não pode ser posterior à final')
      return
    }
    setPeriodError(null)
    setPeriod(next)
  }

  function handleToggle(registro: FrequenciaLer, presente: boolean) {
    save.mutate(
      { matricula_id: registro.matricula_id, data: registro.data, presente },
      {
        onSuccess: () => notifySuccess('Frequência atualizada'),
        onError: (error) => notifyError(error),
      },
    )
  }

  const turmaByMatricula = new Map((enrollments.data ?? []).map((matricula) => [matricula.id, matricula.turma_id]))
  const rows = [...(attendance.data ?? [])].sort((a, b) => b.data.localeCompare(a.data))
  const faltas = rows.filter((registro) => !registro.presente).length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-44">
            <Field label="De">
              <input type="date" value={draft.data_inicio} max={today} onChange={(event) => handleChange('data_inicio', event.target.value)} />
            </Field>
          </div>
          <div className="w-44">
            <Field label="Até">
              <input type="date" value={draft.data_fim} max={today} onChange={(event) => handleChange('data_fim', event.target.value)} />
            </Field>
          </div>
        </div>
        <Badge variant="default">{`${plural(faltas, 'falta', 'faltas')} em ${plural(rows.length, 'registro', 'registros')}`}</Badge>
      </div>
      {periodError && (
        <p role="alert" className="text-caption text-danger">
          {periodError}
        </p>
      )}

      {attendance.isPending || enrollments.isPending ? (
        <PageState status="loading" />
      ) : attendance.isError || enrollments.isError ? (
        <PageState
          status="error"
          error={attendance.error ?? enrollments.error}
          onRetry={() => void attendance.refetch()}
        />
      ) : rows.length === 0 ? (
        <PageState status="empty" emptyText="Nenhum registro de frequência no período" />
      ) : (
        <DataTable
          embedded
          rows={rows}
          columns={[
            { key: 'data', header: 'Data', cell: (registro: FrequenciaLer) => formatDate(registro.data) },
            {
              key: 'turma',
              header: 'Turma',
              cell: (registro: FrequenciaLer) => <ClassNameCell turmaId={turmaByMatricula.get(registro.matricula_id)} />,
            },
            {
              key: 'situacao',
              header: 'Situação',
              cell: (registro: FrequenciaLer) =>
                writable ? (
                  <PresenceToggle
                    label={`Frequência de ${formatDate(registro.data)}`}
                    presente={registro.presente}
                    disabled={save.isPending}
                    onChange={(presente) => handleToggle(registro, presente)}
                  />
                ) : registro.presente ? (
                  <Badge variant="success">Presente</Badge>
                ) : (
                  <Badge variant="destructive">Falta</Badge>
                ),
            },
          ]}
        />
      )}
    </div>
  )
}
