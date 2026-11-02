import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { fetchAllPages } from '@/shared/api/pagination'
import { daysAgoLocal, todayLocal } from '@/shared/lib/format'
import { getAggregate, listEscolas, listParadas, listPolos, listRotas, type Group } from './api'

export type Period = { data_inicio: string; data_fim: string }

export function usePeriod(): Period & { set: (p: Period) => void } {
  const [searchParams, setSearchParams] = useSearchParams()
  const data_inicio = searchParams.get('data_inicio') ?? daysAgoLocal(30)
  const data_fim = searchParams.get('data_fim') ?? todayLocal()

  function set(p: Period) {
    setSearchParams({ data_inicio: p.data_inicio, data_fim: p.data_fim })
  }

  return { data_inicio, data_fim, set }
}

export function useAggregate(group: Group, period: Period, enabled = true) {
  return useQuery({
    queryKey: ['dashboard', 'aggregate', group, period.data_inicio, period.data_fim],
    queryFn: () => getAggregate({ agrupar: group, data_inicio: period.data_inicio, data_fim: period.data_fim }),
    enabled,
  })
}

export function useDashboardSchools(enabled: boolean) {
  return useQuery({
    queryKey: ['dashboard', 'schools'],
    queryFn: () => fetchAllPages((limit, offset) => listEscolas({ limit, offset })),
    enabled,
  })
}

export function useDashboardPoles(enabled: boolean) {
  return useQuery({
    queryKey: ['dashboard', 'poles'],
    queryFn: () => fetchAllPages((limit, offset) => listPolos({ limit, offset })),
    enabled,
  })
}

export function useDashboardRoutes() {
  return useQuery({
    queryKey: ['dashboard', 'routes'],
    queryFn: () => fetchAllPages((limit, offset) => listRotas({ limit, offset })),
  })
}

export function useDashboardStops() {
  return useQuery({
    queryKey: ['dashboard', 'stops'],
    queryFn: () => fetchAllPages((limit, offset) => listParadas({ limit, offset }), 500),
  })
}
