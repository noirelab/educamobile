import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import {
  attachStudent,
  createStop,
  deleteStop,
  detachStudent,
  getStop,
  listStopStudents,
  listStops,
  listStudents,
  nearbyStops,
  patchStop,
} from './api'

type ParadaCriar = components['schemas']['ParadaCriar']
type ParadaAtualizar = components['schemas']['ParadaAtualizar']
type NearbyParams = { latitude: number; longitude: number; raio_m: number; limit: number }

const STOP_PAGE_SIZE = 500
const NEARBY_LIMIT = 50

export function useAllStops(enabled = true) {
  return useQuery({
    queryKey: ['stops', 'all'],
    queryFn: () => fetchAllPages((limit, offset) => listStops({ limit, offset }), STOP_PAGE_SIZE),
    enabled,
  })
}

export function useStop(id: number) {
  return useQuery({
    queryKey: ['stops', 'detail', id],
    queryFn: () => getStop(id),
  })
}

export function useStopStudents(id: number) {
  return useQuery({
    queryKey: ['stops', 'students', id],
    queryFn: () => listStopStudents(id),
  })
}

export function useStudentsPage(pager: { limit: number; offset: number }, enabled: boolean) {
  return useQuery({
    queryKey: ['stops', 'students-page', pager.limit, pager.offset],
    queryFn: () => listStudents({ limit: pager.limit, offset: pager.offset }),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useNearbyStops() {
  return useMutation({
    mutationFn: (params: Omit<NearbyParams, 'limit'>) => nearbyStops({ ...params, limit: NEARBY_LIMIT }),
  })
}

export function useCreateStop() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ParadaCriar) => createStop(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stops'] }),
  })
}

export function usePatchStop() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ParadaAtualizar }) => patchStop(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stops'] }),
  })
}

export function useDeleteStop() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteStop(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stops'] }),
  })
}

export function useAttachStudent(stopId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (studentId: number) => attachStudent(stopId, studentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stops', 'students', stopId] }),
  })
}

export function useDetachStudent(stopId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (studentId: number) => detachStudent(stopId, studentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stops', 'students', stopId] }),
  })
}

export function useStopName(id: number | null): string {
  const query = useAllStops(id !== null)
  if (id === null || !query.data) return '—'
  return query.data.find((stop) => stop.id === id)?.nome ?? '—'
}
