import { CalendarCheck, Pencil, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { StudentAttendance } from '@/features/attendance/components/StudentAttendance'
import { EnrollmentHistory } from '@/features/enrollments/components/EnrollmentHistory'
import { access, canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatDate } from '@/shared/lib/format'
import type { LatLng } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import { notifySuccess } from '@/shared/ui/toast'
import { StudentMiniMap } from '../components/StudentMiniMap'
import { useDeleteStudent, useStopOptions, useStudent } from '../hooks'

function formatCoordinate(value: number): string {
  return value.toFixed(6)
}

function AttendancePlaceholder() {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <CalendarCheck size={32} strokeWidth={1.5} className="text-ink-muted opacity-60" aria-hidden="true" />
      <p className="text-body text-ink-muted">Disponível em breve</p>
    </div>
  )
}

export function StudentDetailPage() {
  const { id } = useParams()
  const studentId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const query = useStudent(studentId)
  const stops = useStopOptions(true)
  const remove = useDeleteStudent()

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const student = query.data
  const canEdit = role !== null && canWrite(role, 'students')
  const canDelete = role === 'admin'
  const canSeeEnrollments = role !== null && access(role, 'enrollments') !== 'none'
  const stop = (stops.data ?? []).find((parada) => parada.id === student.parada_id)
  const residence: LatLng | null = student.localizacao
  const stopPoint: LatLng | null = stop?.localizacao ?? null
  const hasLocation = residence !== null || stopPoint !== null
  const responsavel = student.nome_responsavel ?? '—'

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
          {`Nascimento ${formatDate(student.data_nascimento)} · Responsável ${responsavel}`}
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
              <dt className="text-label text-ink-muted">Responsável</dt>
              <dd className="text-body font-medium text-ink">{responsavel}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Parada</dt>
              <dd className="text-body font-medium text-ink">
                {student.parada_id === null ? 'Sem parada' : (stop?.nome ?? '—')}
              </dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Localização</dt>
              <dd className="font-mono text-[13px] text-ink">
                {residence ? `${formatCoordinate(residence.latitude)}, ${formatCoordinate(residence.longitude)}` : '—'}
              </dd>
            </div>
          </dl>
        </Panel>

        <Panel className="p-2.5 lg:p-2.5">
          {hasLocation ? (
            <StudentMiniMap residence={residence} stop={stopPoint} />
          ) : (
            <PageState status="empty" emptyText="Sem localização cadastrada" />
          )}
        </Panel>
      </div>

      {canSeeEnrollments ? (
        <Panel>
          <Tabs defaultValue="matriculas">
            <TabsList>
              <TabsTrigger value="matriculas">Matrículas</TabsTrigger>
              <TabsTrigger value="frequencia">Frequência</TabsTrigger>
            </TabsList>
            <TabsContent value="matriculas">
              <EnrollmentHistory studentId={student.id} />
            </TabsContent>
            <TabsContent value="frequencia">
              <StudentAttendance studentId={student.id} />
            </TabsContent>
          </Tabs>
        </Panel>
      ) : (
        <Panel title="Frequência">
          <AttendancePlaceholder />
        </Panel>
      )}
    </div>
  )
}
