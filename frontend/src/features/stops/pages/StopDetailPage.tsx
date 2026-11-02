import { Pencil, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { StopMiniMap } from '@/features/stops/components/StopsMap'
import { StopStudents } from '@/features/stops/components/StopStudents'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import type { LatLng } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/ui/dialog'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { useDeleteStop, usePatchStop, useStop } from '../hooks'
import { parseStopName } from '../schemas'

function formatCoordinate(value: number): string {
  return value.toFixed(6)
}

function EditNameDialog({ id, nome }: { id: number; nome: string }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(nome)
  const [error, setError] = useState<string | undefined>(undefined)
  const patch = usePatchStop()

  function handleOpenChange(next: boolean) {
    if (next) {
      setValue(nome)
      setError(undefined)
    }
    setOpen(next)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const parsed = parseStopName(value)
    setError(parsed.error ?? undefined)
    if (parsed.error) return
    try {
      await patch.mutateAsync({ id, body: { nome: parsed.nome } })
      notifySuccess('Parada atualizada')
      setOpen(false)
    } catch (err) {
      notifyError(err)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="secondary">
          <Pencil aria-hidden="true" />
          Editar nome
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Editar nome</DialogTitle>
            <DialogDescription>A localização da parada não muda.</DialogDescription>
          </DialogHeader>
          <FloatingField label="Nome" value={value} error={error} onChange={(event) => setValue(event.target.value)} />
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={patch.isPending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function StopDetailPage() {
  const { id } = useParams()
  const stopId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const canEdit = role !== null && canWrite(role, 'stops')
  const query = useStop(stopId)
  const remove = useDeleteStop()

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const stop = query.data
  const point: LatLng = stop.localizacao

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={stop.nome}
        description="Parada do transporte escolar"
        actions={
          canEdit && (
            <>
              <EditNameDialog id={stop.id} nome={stop.nome} />
              <ConfirmDialog
                trigger={
                  <Button variant="danger-outline">
                    <Trash2 aria-hidden="true" />
                    Excluir
                  </Button>
                }
                title="Excluir parada"
                description="Esta ação não pode ser desfeita."
                confirmLabel="Excluir"
                onConfirm={async () => {
                  await remove.mutateAsync(stop.id)
                  notifySuccess('Parada excluída')
                  navigate('/stops')
                }}
              />
            </>
          )
        }
      >
        <span className="font-mono text-[13px] text-ink-muted">
          {formatCoordinate(point.latitude)}, {formatCoordinate(point.longitude)}
        </span>
      </PageHeader>
      <Panel className="p-2.5 lg:p-2.5">
        <StopMiniMap stop={stop} />
      </Panel>
      <Panel title="Estudantes desta parada">
        <StopStudents stopId={stop.id} canWrite={canEdit} />
      </Panel>
    </div>
  )
}
