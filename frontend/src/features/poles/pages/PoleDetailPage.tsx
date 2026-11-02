import type { UseQueryResult } from '@tanstack/react-query'
import { Pencil, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Polygon } from 'react-leaflet'
import type { components } from '@/shared/api/schema'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { BaseMap } from '@/shared/map/BaseMap'
import { multiPolygonToLatLngs } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { DataTable } from '@/shared/ui/DataTable'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import { notifySuccess } from '@/shared/ui/toast'
import { useDeletePole, usePole, useSchoolsByPole, useSchoolsInArea } from '../hooks'

type EscolaLer = components['schemas']['EscolaLer']

const SCHOOL_COLUMNS = [
  { key: 'nome', header: 'Nome', cell: (school: EscolaLer) => school.nome },
  { key: 'endereco', header: 'Endereço', cell: (school: EscolaLer) => school.endereco ?? '—' },
]

function SchoolsTable({ query, emptyText }: { query: UseQueryResult<EscolaLer[]>; emptyText: string }) {
  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }
  if (query.data.length === 0) return <PageState status="empty" emptyText={emptyText} />
  return <DataTable embedded columns={SCHOOL_COLUMNS} rows={query.data} />
}

function LinkedSchools({ poleId }: { poleId: number }) {
  const query = useSchoolsByPole(poleId)
  return <SchoolsTable query={query} emptyText="Nenhuma escola vinculada" />
}

function SchoolsInArea({ poleId }: { poleId: number }) {
  const query = useSchoolsInArea(poleId)
  return <SchoolsTable query={query} emptyText="Nenhuma escola na área" />
}

export function PoleDetailPage() {
  const { id } = useParams()
  const poleId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const query = usePole(poleId)
  const remove = useDeletePole()
  const canEdit = role !== null && canWrite(role, 'poles')

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const pole = query.data
  const firstPoint = pole.area?.coordinates[0]?.[0]?.[0]
  const center = firstPoint ? { latitude: firstPoint[1], longitude: firstPoint[0] } : undefined

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={pole.nome}
        description="Polo de atendimento do transporte escolar"
        actions={
          canEdit && (
            <>
              <Button asChild variant="secondary">
                <Link to={`/poles/${pole.id}/edit`}>
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
                title="Excluir polo"
                description="Esta ação não pode ser desfeita."
                confirmLabel="Excluir"
                onConfirm={async () => {
                  await remove.mutateAsync(pole.id)
                  notifySuccess('Polo excluído')
                  navigate('/poles')
                }}
              />
            </>
          )
        }
      >
        <span className="font-mono text-[13px] text-ink-muted">Polo #{pole.id}</span>
      </PageHeader>
      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <Panel dense>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Nome</dt>
              <dd className="text-body font-medium text-ink">{pole.nome}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-label text-ink-muted">Área</dt>
              <dd className="text-body font-medium text-ink">{pole.area ? 'Definida' : 'Não definida'}</dd>
            </div>
          </dl>
        </Panel>
        <Panel className="p-2.5 lg:p-2.5">
          <BaseMap center={center} className="h-[220px]">
            {pole.area && <Polygon positions={multiPolygonToLatLngs(pole.area)} />}
          </BaseMap>
        </Panel>
      </div>
      <Panel dense>
        <Tabs defaultValue="linked">
          <TabsList>
            <TabsTrigger value="linked">Escolas vinculadas</TabsTrigger>
            <TabsTrigger value="area">Escolas na área</TabsTrigger>
          </TabsList>
          <TabsContent value="linked">
            <LinkedSchools poleId={pole.id} />
          </TabsContent>
          <TabsContent value="area">
            <SchoolsInArea poleId={pole.id} />
          </TabsContent>
        </Tabs>
      </Panel>
    </div>
  )
}
