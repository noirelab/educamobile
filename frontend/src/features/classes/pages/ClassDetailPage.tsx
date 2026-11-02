import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { CalendarCheck, Pencil, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type { components } from '@/shared/api/schema'
import { access, canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { DataTable } from '@/shared/ui/DataTable'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifySuccess } from '@/shared/ui/toast'
import { TURNO_LABEL } from '../labels'
import { useActiveEnrollments, useClass, useDeleteClass, useSchoolOptions, useStudentsById } from '../hooks'

type MatriculaLer = components['schemas']['MatriculaLer']

type EnrollmentRow = { matricula: MatriculaLer; nome: string | undefined }

function EnrollmentsSection({
  query,
  studentNames,
}: {
  query: UseQueryResult<MatriculaLer[]>
  studentNames: Map<number, string>
}) {
  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }
  if (query.data.length === 0) return <PageState status="empty" emptyText="Nenhum estudante matriculado" />

  const rows: EnrollmentRow[] = query.data.map((matricula) => ({
    matricula,
    nome: studentNames.get(matricula.estudante_id),
  }))

  return (
    <DataTable
      embedded
      columns={[
        {
          key: 'nome',
          header: 'Estudante',
          cell: (row: EnrollmentRow): ReactNode => (
            <Link to={`/students/${row.matricula.estudante_id}`} className="font-semibold text-ink hover:text-accent">
              {row.nome ?? '—'}
            </Link>
          ),
        },
        {
          key: 'desde',
          header: 'Desde',
          cell: (row: EnrollmentRow) => formatDate(row.matricula.data_inicio),
        },
      ]}
      rows={rows}
    />
  )
}

export function ClassDetailPage() {
  const { id } = useParams()
  const turmaId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const query = useClass(turmaId)
  const schools = useSchoolOptions()
  const enrollments = useActiveEnrollments(turmaId)
  const studentIds = enrollments.data?.map((matricula) => matricula.estudante_id) ?? []
  const students = useStudentsById(studentIds)
  const remove = useDeleteClass()
  const canEdit = role !== null && canWrite(role, 'classes')
  const canAttend = role !== null && access(role, 'attendance') !== 'none'

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const turma = query.data
  const schoolName = (schools.data ?? []).find((school) => school.id === turma.escola_id)?.nome ?? '—'
  const studentNames = new Map<number, string>()
  studentIds.forEach((studentId, index) => {
    const nome = students[index]?.data?.nome
    if (nome !== undefined) studentNames.set(studentId, nome)
  })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={turma.nome}
        description="Turma da rede municipal"
        actions={
          <>
            {canAttend && (
              <Button asChild>
                <Link to={`/attendance?turma=${turma.id}`}>
                  <CalendarCheck aria-hidden="true" />
                  Lançar frequência
                </Link>
              </Button>
            )}
            {canEdit && (
              <>
                <Button asChild variant="secondary">
                  <Link to={`/classes/${turma.id}/edit`}>
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
                  title="Excluir turma"
                  description="Esta ação não pode ser desfeita."
                  confirmLabel="Excluir"
                  onConfirm={async () => {
                    await remove.mutateAsync(turma.id)
                    notifySuccess('Turma excluída')
                    navigate('/classes')
                  }}
                />
              </>
            )}
          </>
        }
      >
        <span className="text-caption text-ink-muted">
          {`${turma.serie} · ${TURNO_LABEL[turma.turno]} · ${turma.ano_letivo}`}
        </span>
      </PageHeader>
      <Panel dense>
        <dl className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1">
            <dt className="text-label text-ink-muted">Escola</dt>
            <dd className="text-body font-medium text-ink">{schoolName}</dd>
          </div>
        </dl>
      </Panel>
      <Panel dense title="Matriculados">
        <EnrollmentsSection query={enrollments} studentNames={studentNames} />
      </Panel>
    </div>
  )
}
