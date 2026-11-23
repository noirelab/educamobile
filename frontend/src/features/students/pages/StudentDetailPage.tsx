import { Pencil, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useSchool } from '@/features/schools/hooks'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifySuccess } from '@/shared/ui/toast'
import { StudentMiniMap } from '../components/StudentMiniMap'
import { useDeleteStudent, useStopOptions, useStudent } from '../hooks'
import { TURNO_LABEL } from '../schemas'

export function StudentDetailPage() {
  const { id } = useParams()
  const studentId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const query = useStudent(studentId)
  const stops = useStopOptions(true)
  const school = useSchool(query.data?.escola_id ?? 0)
  const remove = useDeleteStudent()

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const student = query.data
  const canEdit = role !== null && canWrite(role, 'students')
  const canDelete = role === 'admin'
  const stop = (stops.data ?? []).find((parada) => parada.id === student.parada_id)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={student.nome}
        actions={
          <>
            {canEdit && (
              <Button asChild variant="secondary">
                <Link to={`/students/${student.id}/edit`}>
                  <Pencil aria-hidden="true" />
                  Editar
                </Link>
              </Button>
            )}
            {canDelete && (
              <ConfirmDialog
                trigger={
                  <Button variant="danger-outline">
                    <Trash2 aria-hidden="true" />
                    Excluir
                  </Button>
                }
                title="Excluir estudante"
                description="Esta ação não pode ser desfeita."
                confirmLabel="Excluir"
                onConfirm={async () => {
                  await remove.mutateAsync(student.id)
                  notifySuccess('Estudante excluído')
                  navigate('/students')
                }}
              />
            )}
          </>
        }
      >
        <span className="font-mono text-[13px] text-ink-muted">
          {`Nascimento ${formatDate(student.data_nascimento)}`}
        </span>
      </PageHeader>

      <div className="grid items-start gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Panel title="Dados">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Nascimento</dt>
              <dd className="text-body font-medium text-ink">{formatDate(student.data_nascimento)}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Turno</dt>
              <dd className="text-body font-medium text-ink">{TURNO_LABEL[student.turno]}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Escola</dt>
              <dd className="text-body font-medium text-ink">{school.data?.nome ?? '—'}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Parada</dt>
              <dd className="text-body font-medium text-ink">
                {student.parada_id === null ? 'Sem parada' : (stop?.nome ?? '—')}
              </dd>
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2">
              <dt className="text-label text-ink-muted">Observações de cuidado</dt>
              <dd className="text-body font-medium text-ink">{student.observacoes_cuidado ?? '—'}</dd>
            </div>
          </dl>
        </Panel>

        <Panel className="p-2.5 lg:p-2.5">
          {stop ? (
            <StudentMiniMap stop={stop.localizacao} />
          ) : (
            <PageState status="empty" emptyText="Sem parada associada" />
          )}
        </Panel>
      </div>
    </div>
  )
}
