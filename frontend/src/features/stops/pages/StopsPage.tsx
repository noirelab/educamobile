import { ChevronRight, Plus, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { NearbySearch, type NearbyFilter } from '@/features/stops/components/NearbySearch'
import { StopsMap } from '@/features/stops/components/StopsMap'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import type { LatLng } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Reveal } from '@/shared/ui/Reveal'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { useAllStops, useCreateStop, usePatchStop } from '../hooks'
import { parseStopName } from '../schemas'

export function StopsPage() {
  const { role } = useAuth()
  const canEdit = role !== null && canWrite(role, 'stops')
  const stops = useAllStops()
  const create = useCreateStop()
  const patch = usePatchStop()
  const [creating, setCreating] = useState(false)
  const [point, setPoint] = useState<LatLng | null>(null)
  const [prefill, setPrefill] = useState<LatLng | null>(null)
  const [nearby, setNearby] = useState<NearbyFilter | null>(null)
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState<string | undefined>(undefined)

  function handleMapClick(next: LatLng) {
    if (creating && canEdit) {
      setPoint(next)
      setName('')
      setNameError(undefined)
      return
    }
    setPrefill(next)
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (point === null) return
    const parsed = parseStopName(name)
    setNameError(parsed.error ?? undefined)
    if (parsed.error) return
    try {
      await create.mutateAsync({ nome: parsed.nome, localizacao: point })
      notifySuccess('Parada criada')
      setPoint(null)
      setCreating(false)
    } catch (error) {
      notifyError(error)
    }
  }

  function handleMove(stop: { id: number }, next: LatLng) {
    patch.mutate(
      { id: stop.id, body: { localizacao: next } },
      {
        onSuccess: () => notifySuccess('Parada movida'),
        onError: (error) => notifyError(error),
      },
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Paradas"
        description="Pontos de embarque do transporte escolar"
        actions={
          canEdit && (
            <Button variant={creating ? 'secondary' : 'default'} onClick={() => setCreating((value) => !value)}>
              {creating ? <X aria-hidden="true" /> : <Plus aria-hidden="true" />}
              {creating ? 'Cancelar' : 'Nova parada'}
            </Button>
          )
        }
      />
      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr] lg:items-start">
        <Panel className="p-2.5 lg:p-2.5">
          {stops.isPending && <PageState status="loading" />}
          {stops.isError && (
            <PageState status="error" error={stops.error} onRetry={() => void stops.refetch()} />
          )}
          {stops.isSuccess && (
            <div className="relative">
              <StopsMap
                stops={stops.data}
                draggable={canEdit}
                nearby={nearby}
                onMapClick={handleMapClick}
                onMove={handleMove}
              />
              {creating && (
                <span
                  role="status"
                  className="glass-strong absolute left-3 top-3 z-[500] rounded-[12px] px-3 py-1.5 text-caption text-ink"
                >
                  Clique no mapa para posicionar
                </span>
              )}
            </div>
          )}
        </Panel>
        <div className="flex flex-col gap-5">
          <NearbySearch prefill={prefill} onSearch={setNearby} />
          <Panel title="Paradas">
            {stops.isPending && <PageState status="loading" />}
            {stops.isError && (
              <PageState status="error" error={stops.error} onRetry={() => void stops.refetch()} />
            )}
            {stops.isSuccess && stops.data.length === 0 && (
              <PageState status="empty" emptyText="Nenhuma parada cadastrada" />
            )}
            {stops.isSuccess && stops.data.length > 0 && (
              <ul role="list" aria-label="Paradas" className="max-h-[460px] divide-y divide-line overflow-y-auto">
                {stops.data.map((stop, index) => (
                  <li key={stop.id}>
                    <Reveal index={index}>
                      <Link
                        to={`/stops/${stop.id}`}
                        className="flex min-h-[52px] items-center justify-between gap-3 px-2 py-3 text-body font-semibold text-ink transition-colors duration-250 hover:bg-[rgba(15,118,110,.06)]"
                      >
                        {stop.nome}
                        <ChevronRight size={16} className="shrink-0 text-ink-muted" aria-hidden="true" />
                      </Link>
                    </Reveal>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
      <Dialog open={point !== null} onOpenChange={(open) => {
          if (!open) setPoint(null)
        }}>
        <DialogContent>
          <form onSubmit={handleCreate} noValidate className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Nova parada</DialogTitle>
              <DialogDescription>Confira o nome e a localização marcada no mapa.</DialogDescription>
            </DialogHeader>
            <FloatingField
              label="Nome"
              value={name}
              error={nameError}
              onChange={(event) => setName(event.target.value)}
            />
            {point && (
              <dl className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <dt className="text-label text-ink-muted">Latitude</dt>
                  <dd className="font-mono text-[13px] text-ink">{point.latitude}</dd>
                </div>
                <div className="flex flex-col gap-1">
                  <dt className="text-label text-ink-muted">Longitude</dt>
                  <dd className="font-mono text-[13px] text-ink">{point.longitude}</dd>
                </div>
              </dl>
            )}
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setPoint(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending}>
                Salvar
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
