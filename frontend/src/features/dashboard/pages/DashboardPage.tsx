import { useState } from 'react'
import { MapPin, Route, Ruler } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDate, formatMeters } from '@/shared/lib/format'
import { useAuth } from '@/shared/auth/useAuth'
import { BaseMap } from '@/shared/map/BaseMap'
import { Button } from '@/shared/ui/button'
import { KpiCard } from '@/shared/ui/KpiCard'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { Reveal } from '@/shared/ui/Reveal'
import { Skeleton } from '@/shared/ui/Skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/shared/ui/tabs'
import { InfrequencyChart } from '../components/InfrequencyChart'
import { InfrequencyHeatmap } from '../components/InfrequencyHeatmap'
import { KpiCards } from '../components/KpiCards'
import { MapLegend } from '../components/MapLegend'
import { PeriodFilter } from '../components/PeriodFilter'
import { PoleLayer } from '../components/PoleLayer'
import { RoutesMiniMap } from '../components/RoutesMiniMap'
import { SchoolRanking } from '../components/SchoolRanking'
import { heatPoints } from '../heat'
import {
  useAggregate,
  useDashboardPoles,
  useDashboardRoutes,
  useDashboardSchools,
  useDashboardStops,
  usePeriod,
} from '../hooks'
import { summarize } from '../summary'

type MapMode = 'escolas' | 'polos'

const SUBTITLES = {
  admin: 'Infrequência da rede',
  diretor: 'Infrequência da escola',
  coordenador: 'Transporte escolar',
} as const

const count = new Intl.NumberFormat('pt-BR')

function InfrequencyDashboard({ isAdmin }: { isAdmin: boolean }) {
  const period = usePeriod()
  const [mapMode, setMapMode] = useState<MapMode>('escolas')
  const main = useAggregate(isAdmin ? 'polo' : 'turma', period)
  const escolaRows = useAggregate('escola', period, isAdmin)
  const schools = useDashboardSchools(isAdmin)
  const poles = useDashboardPoles(isAdmin)

  const rows = main.data ?? []
  const summary = main.data ? summarize(main.data) : undefined
  const isEmpty = main.isSuccess && summary?.total_registros === 0
  const heat = schools.data && escolaRows.data ? heatPoints(schools.data, escolaRows.data) : null
  const semArea = poles.data?.filter((pole) => pole.area === null) ?? []
  const mapLoading = isAdmin && (schools.isPending || escolaRows.isPending || poles.isPending)

  return (
    <>
      <Reveal index={0}>
        <KpiCards summary={summary} loading={main.isPending} />
      </Reveal>
      {main.isError && (
        <Reveal index={1}>
          <Panel>
            <PageState status="error" error={main.error} onRetry={() => void main.refetch()} />
          </Panel>
        </Reveal>
      )}
      {isAdmin && !main.isError && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.6fr_1fr]">
          <Reveal index={1}>
            <Panel
              title="Mapa de infrequência"
              caption={mapMode === 'escolas' ? 'Escolas com localização' : 'Polos por área de atendimento'}
              actions={
                <Tabs value={mapMode} onValueChange={(value) => setMapMode(value as MapMode)}>
                  <TabsList>
                    <TabsTrigger value="escolas">Escolas</TabsTrigger>
                    <TabsTrigger value="polos">Polos</TabsTrigger>
                  </TabsList>
                </Tabs>
              }
              className="flex flex-col gap-3"
            >
              {isEmpty ? (
                <PageState
                  status="empty"
                  emptyText={`Nenhum registro de frequência entre ${formatDate(period.data_inicio)} e ${formatDate(period.data_fim)}`}
                />
              ) : mapLoading ? (
                <Skeleton className="h-[420px] w-full rounded-[18px]" />
              ) : (
                <div className="relative">
                  <BaseMap className="h-[420px]">
                    {mapMode === 'escolas' ? (
                      schools.data && escolaRows.data ? (
                        <InfrequencyHeatmap schools={schools.data} rows={escolaRows.data} />
                      ) : null
                    ) : poles.data ? (
                      <PoleLayer poles={poles.data} rows={rows} />
                    ) : null}
                  </BaseMap>
                  <MapLegend />
                </div>
              )}
              {heat && heat.missing > 0 && (
                <p className="text-caption text-ink-muted">{`${heat.missing} escolas sem localização`}</p>
              )}
              {mapMode === 'polos' && semArea.length > 0 && (
                <p className="text-caption text-ink-muted">{`Sem área: ${semArea.map((pole) => pole.nome).join(', ')}`}</p>
              )}
            </Panel>
          </Reveal>
          {!isEmpty && escolaRows.data && (
            <Reveal index={2}>
              <SchoolRanking rows={escolaRows.data} />
            </Reveal>
          )}
        </div>
      )}
      {!isAdmin && isEmpty && (
        <Reveal index={1}>
          <Panel>
            <PageState
              status="empty"
              emptyText={`Nenhum registro de frequência entre ${formatDate(period.data_inicio)} e ${formatDate(period.data_fim)}`}
            />
          </Panel>
        </Reveal>
      )}
      {!isEmpty && !main.isError && (
        <Reveal index={3}>
          <InfrequencyChart period={period} groups={isAdmin ? ['polo', 'escola', 'turma'] : ['turma']} />
        </Reveal>
      )}
    </>
  )
}

function LogisticsDashboard() {
  const routes = useDashboardRoutes()
  const stops = useDashboardStops()
  const totalMeters = routes.data
    ? routes.data.reduce((sum, route) => sum + (route.distancia_m ?? 0), 0)
    : null

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Reveal index={0}>
          <KpiCard
            label="Rotas"
            icon={Route}
            loading={routes.isPending}
            value={routes.data ? count.format(routes.data.length) : '—'}
          />
        </Reveal>
        <Reveal index={1}>
          <KpiCard
            label="Paradas"
            icon={MapPin}
            loading={stops.isPending}
            value={stops.data ? count.format(stops.data.length) : '—'}
          />
        </Reveal>
        <Reveal index={2}>
          <KpiCard
            label="Distância total"
            icon={Ruler}
            loading={routes.isPending}
            value={totalMeters === null ? '—' : formatMeters(totalMeters)}
          />
        </Reveal>
      </div>
      {routes.isError && (
        <Reveal index={3}>
          <Panel>
            <PageState status="error" error={routes.error} onRetry={() => void routes.refetch()} />
          </Panel>
        </Reveal>
      )}
      {routes.data && (
        <Reveal index={3}>
          <Panel
            title="Mapa das rotas"
            actions={
              <Button variant="secondary" asChild>
                <Link to="/routes">Ver rotas</Link>
              </Button>
            }
          >
            <RoutesMiniMap routes={routes.data} />
          </Panel>
        </Reveal>
      )}
    </>
  )
}

export function DashboardPage() {
  const { role } = useAuth()
  if (role === null) return null

  if (role === 'coordenador') {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Painel" description={SUBTITLES.coordenador} />
        <LogisticsDashboard />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Painel"
        description={SUBTITLES[role]}
        actionsAtLg={role === 'admin'}
        actions={<PeriodFilter />}
      />
      <InfrequencyDashboard isAdmin={role === 'admin'} />
    </div>
  )
}
