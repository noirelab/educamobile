import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Marker } from 'react-leaflet'
import { Pencil, Trash2 } from 'lucide-react'
import type { components } from '@/shared/api/schema'
import { access, canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { BaseMap } from '@/shared/map/BaseMap'
import { toLeaflet } from '@/shared/map/geo'
import { daysAgoLocal, formatPercent, todayLocal } from '@/shared/lib/format'
import { rateColor } from '@/shared/lib/heat'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { DataTable } from '@/shared/ui/DataTable'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifySuccess } from '@/shared/ui/toast'
import { useClassAttendance, useDeleteSchool, usePoleOptions, useSchool, useSchoolClasses, useSchoolTeachers } from '../hooks'

type TurmaLer = components['schemas']['TurmaLer']
type ProfessorLer = components['schemas']['ProfessorLer']
type FrequenciaAgregada = components['schemas']['FrequenciaAgregada']

const TURNO_LABEL: Record<TurmaLer['turno'], string> = {
  manha: 'Manhã',
  tarde: 'Tarde',
  noite: 'Noite',
  integral: 'Integral',
}

const CLASS_COLUMNS = [
  { key: 'nome', header: 'Nome', cell: (turma: TurmaLer) => turma.nome },
  { key: 'serie', header: 'Série', cell: (turma: TurmaLer) => turma.serie },
  { key: 'turno', header: 'Turno', cell: (turma: TurmaLer) => TURNO_LABEL[turma.turno] },
  { key: 'ano', header: 'Ano letivo', cell: (turma: TurmaLer) => turma.ano_letivo },
]

const TEACHER_COLUMNS = [
  { key: 'nome', header: 'Nome', cell: (professor: ProfessorLer) => professor.nome },
  { key: 'email', header: 'E-mail', cell: (professor: ProfessorLer) => professor.email },
]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Panel dense title={title}>
      {children}
    </Panel>
  )
}

function QuerySection<T>({
  query,
  columns,
  emptyText,
}: {
  query: UseQueryResult<T[]>
  columns: { key: string; header: string; cell: (row: T) => ReactNode }[]
  emptyText: string
}) {
  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }
  if (query.data.length === 0) return <PageState status="empty" emptyText={emptyText} />
  return <DataTable embedded columns={columns} rows={query.data} />
}

function AttendanceSection({ query }: { query: UseQueryResult<FrequenciaAgregada[]> }) {
  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }
  if (query.data.length === 0) {
    return <PageState status="empty" emptyText="Nenhum registro de frequência no período" />
  }
  return (
    <ul role="list" className="flex flex-col gap-4">
      {query.data.map((row) => {
        const width = Math.min(100, row.taxa_infrequencia * 100)
        const tone =
          row.taxa_infrequencia >= 0.4 ? 'text-danger' : row.taxa_infrequencia >= 0.2 ? 'text-warning-text' : 'text-ink'
        return (
          <li key={row.grupo_id ?? row.grupo_nome} className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-3 text-body">
              <span className="text-ink">{row.grupo_nome ?? '—'}</span>
              <span className={`font-semibold tabular-nums ${tone}`}>{formatPercent(row.taxa_infrequencia)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[rgba(15,30,51,0.08)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${width}%`, backgroundColor: rateColor(row.taxa_infrequencia) }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export function SchoolDetailPage() {
  const { id } = useParams()
  const schoolId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const query = useSchool(schoolId)
  const poles = usePoleOptions()
  const classes = useSchoolClasses(schoolId)
  const showTeachers = role !== null && access(role, 'teachers') !== 'none'
  const teachers = useSchoolTeachers(schoolId, showTeachers)
  const showAttendance = role === 'diretor'
  const attendance = useClassAttendance(daysAgoLocal(30), todayLocal(), showAttendance)
  const remove = useDeleteSchool()
  const canEdit = role !== null && canWrite(role, 'schools')

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const school = query.data
  const poleName = school.polo_id === null ? '—' : (poles.data?.find((pole) => pole.id === school.polo_id)?.nome ?? '—')

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={school.nome}
        description="Escola da rede municipal"
        actions={
          canEdit && (
            <>
              <Button asChild variant="secondary">
                <Link to={`/schools/${school.id}/edit`}>
                  <Pencil aria-hidden="true" />
                  Editar
                </Link>
              </Button>
              <ConfirmDialog
                trigger={
                  <Button variant="danger-outline">
                    <Trash2 aria-hidden="true" />
                    Excluir
                  </Button>
                }
                title="Excluir escola"
                description="Esta ação não pode ser desfeita."
                confirmLabel="Excluir"
                onConfirm={async () => {
                  await remove.mutateAsync(school.id)
                  notifySuccess('Escola excluída')
                  navigate('/schools')
                }}
              />
            </>
          )
        }
      >
        <span className="font-mono text-[13px] text-ink-muted">INEP {school.codigo_inep ?? '—'}</span>
      </PageHeader>
      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <Panel dense>
          <dl className="grid gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">INEP</dt>
              <dd className="font-mono text-[13px] text-ink">{school.codigo_inep ?? '—'}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Polo</dt>
              <dd className="text-body font-medium text-ink">{poleName}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Endereço</dt>
              <dd className="text-body font-medium text-ink">{school.endereco ?? '—'}</dd>
            </div>
          </dl>
        </Panel>
        <Panel className="p-2.5 lg:p-2.5">
          <BaseMap center={school.localizacao} className="h-[220px]">
            <Marker position={toLeaflet(school.localizacao)} />
          </BaseMap>
        </Panel>
      </div>
      <Section title="Turmas">
        <QuerySection query={classes} columns={CLASS_COLUMNS} emptyText="Nenhuma turma cadastrada" />
      </Section>
      {showTeachers && (
        <Section title="Professores">
          <QuerySection query={teachers} columns={TEACHER_COLUMNS} emptyText="Nenhum professor cadastrado" />
        </Section>
      )}
      {showAttendance && (
        <Section title="Infrequência por turma">
          <AttendanceSection query={attendance} />
        </Section>
      )}
    </div>
  )
}
