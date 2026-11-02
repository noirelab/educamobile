import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import {
  createPole,
  deletePole,
  getPole,
  listPoles,
  listSchoolsByPole,
  listSchoolsInArea,
  updatePole,
} from './api'

type PoloCriar = components['schemas']['PoloCriar']

type PageParams = { limit: number; offset: number }

export function usePoles(pager: PageParams) {
  return useQuery({
    queryKey: ['poles', 'list', pager.limit, pager.offset],
    queryFn: () => listPoles({ limit: pager.limit, offset: pager.offset }),
    placeholderData: keepPreviousData,
  })
}

export function useAllPoles() {
  return useQuery({
    queryKey: ['poles', 'all'],
    queryFn: () => fetchAllPages((limit, offset) => listPoles({ limit, offset })),
  })
}

export function usePole(id: number) {
  return useQuery({
    queryKey: ['poles', 'detail', id],
    queryFn: () => getPole(id),
  })
}

export function useSchoolsByPole(id: number) {
  return useQuery({
    queryKey: ['poles', 'schools', id],
    queryFn: () => fetchAllPages((limit, offset) => listSchoolsByPole(id, { limit, offset })),
  })
}

export function useSchoolsInArea(id: number) {
  return useQuery({
    queryKey: ['poles', 'schools-in-area', id],
    queryFn: () => listSchoolsInArea(id),
  })
}

export function useSavePole(id?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: PoloCriar) => (id === undefined ? createPole(body) : updatePole(id, body)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['poles'], refetchType: 'none' }),
  })
}

export function useDeletePole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deletePole(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['poles'], refetchType: 'none' }),
  })
}
