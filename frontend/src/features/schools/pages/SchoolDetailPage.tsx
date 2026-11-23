import { Link, useNavigate, useParams } from 'react-router-dom'
import { Marker } from 'react-leaflet'
import { Pencil, Trash2 } from 'lucide-react'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { BaseMap } from '@/shared/map/BaseMap'
import { toLeaflet } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifySuccess } from '@/shared/ui/toast'
import { useDeleteSchool, useSchool } from '../hooks'

export function SchoolDetailPage() {
  const { id } = useParams()
  const schoolId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const query = useSchool(schoolId)
  const remove = useDeleteSchool()
  const canEdit = role !== null && canWrite(role, 'schools')

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const school = query.data

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
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">INEP</dt>
              <dd className="font-mono text-[13px] text-ink">{school.codigo_inep ?? '—'}</dd>
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
    </div>
  )
}
