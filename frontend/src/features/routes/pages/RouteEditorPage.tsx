import { Info, Pencil, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '@/shared/api/errors'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatMeters } from '@/shared/lib/format'
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
import { PageState } from '@/shared/ui/PageState'
import { Panel } from '@/shared/ui/Panel'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { RouteEditorMap } from '../components/RoutesMap'
import { StopSequence } from '../components/StopSequence'
import { useDeleteRoute, useEditorStops, useRenameRoute, useRoute, useSetRouteStops } from '../hooks'
import { parseRouteName } from '../schemas'
import { addStop, sameIds } from '../sequence'

type SaveResult = { before: number | null; after: number | null }

function RenameRouteDialog({ id, nome }: { id: number; nome: string }) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(nome)
  const [error, setError] = useState<string | undefined>(undefined)
  const rename = useRenameRoute()

  function handleOpenChange(next: boolean) {
    if (next) {
      setValue(nome)
      setError(undefined)
    }
    setOpen(next)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const parsed = parseRouteName(value)
    setError(parsed.error ?? undefined)
    if (parsed.error) return
    try {
      await rename.mutateAsync({ id, body: { nome: parsed.nome } })
      notifySuccess('Rota renomeada')
      setOpen(false)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Conflito com outra rota')
        return
      }
      notifyError(err)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="secondary">
          <Pencil aria-hidden="true" />
          Renomear
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Renomear rota</DialogTitle>
            <DialogDescription>O nome precisa ser único entre as rotas.</DialogDescription>
          </DialogHeader>
          <FloatingField label="Nome" value={value} error={error} onChange={(event) => setValue(event.target.value)} />
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={rename.isPending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function RouteEditorPage() {
  const { id } = useParams()
  const routeId = Number(id)
  const navigate = useNavigate()
  const { role } = useAuth()
  const canEdit = role !== null && canWrite(role, 'routes')
  const query = useRoute(routeId)
  const stopsQuery = useEditorStops()
  const save = useSetRouteStops()
  const remove = useDeleteRoute()
  const [draft, setDraft] = useState<number[] | null>(null)
  const [result, setResult] = useState<SaveResult | null>(null)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) {
    return <PageState status="error" error={query.error} onRetry={() => void query.refetch()} />
  }

  const route = query.data
  const savedIds = route.paradas.map((stop) => stop.id)
  const current = draft ?? savedIds
  const dirty = !sameIds(current, savedIds)

  const names = new Map<number, string>()
  for (const stop of stopsQuery.data ?? []) names.set(stop.id, stop.nome)
  for (const stop of route.paradas) names.set(stop.id, stop.nome)

  function handleAdd(stopId: number) {
    if (!canEdit) return
    setDraft(addStop(current, stopId))
  }

  async function handleSave() {
    const before = route.distancia_m
    try {
      const updated = await save.mutateAsync({ id: route.id, parada_ids: current })
      setDraft(null)
      setResult({ before, after: updated.distancia_m })
    } catch (error) {
      notifyError(error)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={route.nome}
        description="Sequência de paradas do transporte escolar"
        actions={
          canEdit && (
            <>
              <RenameRouteDialog id={route.id} nome={route.nome} />
              <ConfirmDialog
                trigger={
                  <Button variant="danger-outline">
                    <Trash2 aria-hidden="true" />
                    Excluir
                  </Button>
                }
                title="Excluir rota"
                description="Esta ação não pode ser desfeita."
                confirmLabel="Excluir"
                onConfirm={async () => {
                  await remove.mutateAsync(route.id)
                  notifySuccess('Rota excluída')
                  navigate('/routes')
                }}
              />
            </>
          )
        }
      >
        <span className="glass-strong inline-flex items-center gap-2 rounded-[12px] px-3 py-1.5 text-caption text-ink-muted">
          <Info size={16} strokeWidth={1.75} aria-hidden="true" className="text-accent" />
          Trajeto em linha reta entre paradas
        </span>
      </PageHeader>
      <div className="grid gap-5 lg:grid-cols-[1fr_1.6fr] lg:items-start">
        <Panel title="Sequência de paradas">
          {current.length === 0 ? (
            <p className="px-1 py-6 text-center text-body text-ink-muted">
              {canEdit ? 'Adicione paradas clicando no mapa' : 'Nenhuma parada nesta rota'}
            </p>
          ) : (
            <StopSequence ids={current} names={names} readOnly={!canEdit} onChange={setDraft} />
          )}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <div className="flex flex-col gap-2">
              <span className="text-caption text-ink-muted">
                Distância atual:{' '}
                <span className="font-semibold text-ink tabular-nums">{formatMeters(route.distancia_m)}</span>
              </span>
              {result && (
                <span
                  role="status"
                  className={
                    result.before !== null && result.after !== null && result.after < result.before
                      ? 'inline-flex w-fit rounded-[10px] bg-[rgba(22,163,74,0.15)] px-2.5 py-1 text-caption font-semibold text-[#166534] tabular-nums'
                      : result.before !== null && result.after !== null && result.after > result.before
                        ? 'inline-flex w-fit rounded-[10px] bg-[rgba(220,38,38,0.10)] px-2.5 py-1 text-caption font-semibold text-[#b91c1c] tabular-nums'
                        : 'inline-flex w-fit rounded-[10px] bg-accent-soft px-2.5 py-1 text-caption font-semibold text-ink tabular-nums'
                  }
                >
                  {formatMeters(result.before)} → {formatMeters(result.after)}
                </span>
              )}
            </div>
            {canEdit && (
              <Button onClick={() => void handleSave()} disabled={!dirty || save.isPending}>
                Salvar sequência
              </Button>
            )}
          </div>
        </Panel>
        <Panel className="p-2.5 lg:p-2.5">
          {stopsQuery.isPending && <PageState status="loading" />}
          {stopsQuery.isError && (
            <PageState status="error" error={stopsQuery.error} onRetry={() => void stopsQuery.refetch()} />
          )}
          {stopsQuery.isSuccess && (
            <RouteEditorMap
              stops={stopsQuery.data}
              sequence={current}
              trajeto={route.trajeto}
              routeId={route.id}
              canEdit={canEdit}
              onAdd={handleAdd}
            />
          )}
        </Panel>
      </div>
    </div>
  )
}
