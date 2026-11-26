import { ChevronRight, Info, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { canWrite } from '@/shared/auth/permissions'
import { useAuth } from '@/shared/auth/useAuth'
import { formatMeters } from '@/shared/lib/format'
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
import { PageState } from '@/shared/ui/PageState'
import { Panel } from '@/shared/ui/Panel'
import { Reveal } from '@/shared/ui/Reveal'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { RoutesMap } from '../components/RoutesMap'
import { useAllSchools } from '@/features/schools/hooks'
import { Field } from '@/shared/ui/Field'
import { useAllRoutes, useCreateRoute } from '../hooks'
import { parseRouteName } from '../schemas'
import { routeColor } from '../sequence'

export function RoutesPage() {
  const { role } = useAuth()
  const canEdit = role !== null && canWrite(role, 'routes')
  const navigate = useNavigate()
  const routes = useAllRoutes()
  const create = useCreateRoute()
  const [creating, setCreating] = useState(false)
  const schools = useAllSchools()
  const [name, setName] = useState('')
  const [escolaId, setEscolaId] = useState('')
  const [turno, setTurno] = useState<'manha' | 'tarde'>('manha')
  const [sentido, setSentido] = useState<'ida' | 'volta'>('ida')
  const [escolaError, setEscolaError] = useState<string | undefined>(undefined)
  const [nameError, setNameError] = useState<string | undefined>(undefined)

  function handleOpenChange(next: boolean) {
    if (next) {
      setName('')
      setNameError(undefined)
      setEscolaId('')
      setEscolaError(undefined)
    }
    setCreating(next)
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    const parsed = parseRouteName(name)
    setNameError(parsed.error ?? undefined)
    setEscolaError(escolaId === '' ? 'Informe a escola' : undefined)
    if (parsed.error || escolaId === '') return
    try {
      const route = await create.mutateAsync({
        nome: parsed.nome,
        escola_id: Number(escolaId),
        turno,
        sentido,
      })
      notifySuccess('Rota criada')
      setCreating(false)
      navigate(`/routes/${route.id}`)
    } catch (error) {
      notifyError(error)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Rotas"
        description="Trajetos do transporte escolar (US03)"
        actions={
          canEdit && (
            <Button onClick={() => handleOpenChange(true)}>
              <Plus aria-hidden="true" />
              Nova rota
            </Button>
          )
        }
      >
        <span className="glass-strong inline-flex items-center gap-2 rounded-[12px] px-3 py-1.5 text-caption text-ink-muted">
          <Info size={16} strokeWidth={1.75} aria-hidden="true" className="text-accent" />
          Trajeto em linha reta entre paradas
        </span>
      </PageHeader>
      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr] lg:items-start">
        <Panel className="p-2.5 lg:p-2.5">
          {routes.isPending && <PageState status="loading" />}
          {routes.isError && (
            <PageState status="error" error={routes.error} onRetry={() => void routes.refetch()} />
          )}
          {routes.isSuccess && <RoutesMap routes={routes.data} />}
        </Panel>
        <Panel title="Rotas">
          {routes.isPending && <PageState status="loading" />}
          {routes.isError && (
            <PageState status="error" error={routes.error} onRetry={() => void routes.refetch()} />
          )}
          {routes.isSuccess && routes.data.length === 0 && (
            <PageState status="empty" emptyText="Nenhuma rota cadastrada" />
          )}
          {routes.isSuccess && routes.data.length > 0 && (
            <ul role="list" aria-label="Rotas" className="max-h-[460px] divide-y divide-line overflow-y-auto">
              {routes.data.map((route, index) => (
                <li key={route.id}>
                  <Reveal index={index}>
                    <Link
                      to={`/routes/${route.id}`}
                      className="flex min-h-[52px] items-center gap-3 px-2 py-3 transition-colors duration-250 hover:bg-[rgba(15,118,110,.06)]"
                    >
                      <span
                        aria-hidden="true"
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{ backgroundColor: routeColor(route.id) }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-body font-semibold text-ink">{route.nome}</span>
                        <span className="block text-caption text-ink-muted tabular-nums">
                          {route.paradas.length === 1 ? '1 parada' : `${route.paradas.length} paradas`} ·{' '}
                          {formatMeters(route.distancia_m)}
                        </span>
                      </span>
                      <ChevronRight size={16} className="shrink-0 text-ink-muted" aria-hidden="true" />
                    </Link>
                  </Reveal>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <Dialog open={creating} onOpenChange={handleOpenChange}>
        <DialogContent>
          <form onSubmit={handleCreate} noValidate className="flex flex-col gap-4">
            <DialogHeader>
              <DialogTitle>Nova rota</DialogTitle>
              <DialogDescription>Depois de criar, você monta a sequência de paradas.</DialogDescription>
            </DialogHeader>
            <FloatingField
              label="Nome"
              value={name}
              error={nameError}
              onChange={(event) => setName(event.target.value)}
            />
            <Field label="Escola de destino" error={escolaError}>
              <select value={escolaId} onChange={(event) => setEscolaId(event.target.value)}>
                <option value="">Selecione a escola</option>
                {(schools.data ?? []).map((escola) => (
                  <option key={escola.id} value={String(escola.id)}>
                    {escola.nome}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid gap-x-4 sm:grid-cols-2">
              <Field label="Turno">
                <select value={turno} onChange={(event) => setTurno(event.target.value as 'manha' | 'tarde')}>
                  <option value="manha">Manhã</option>
                  <option value="tarde">Tarde</option>
                </select>
              </Field>
              <Field label="Sentido">
                <select value={sentido} onChange={(event) => setSentido(event.target.value as 'ida' | 'volta')}>
                  <option value="ida">Ida (casa para a escola)</option>
                  <option value="volta">Volta (escola para casa)</option>
                </select>
              </Field>
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending}>
                Criar
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
