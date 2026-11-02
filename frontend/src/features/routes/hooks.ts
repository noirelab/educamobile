import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import {
  createRoute,
  deleteRoute,
  getRoute,
  listEditorStops,
  listRoutes,
  renameRoute,
  setRouteStops,
} from './api'

type RotaCriar = components['schemas']['RotaCriar']
type RotaAtualizar = components['schemas']['RotaAtualizar']

const ROUTE_PAGE_SIZE = 200

export function useAllRoutes() {
  return useQuery({
    queryKey: ['routes', 'all'],
    queryFn: () => fetchAllPages((limit, offset) => listRoutes({ limit, offset }), ROUTE_PAGE_SIZE),
  })
}

export function useRoute(id: number) {
  return useQuery({
    queryKey: ['routes', 'detail', id],
    queryFn: () => getRoute(id),
  })
}

export function useEditorStops() {
  return useQuery({
    queryKey: ['routes', 'editor-stops'],
    queryFn: () => listEditorStops(),
  })
}

export function useCreateRoute() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: RotaCriar) => createRoute(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['routes', 'all'] }),
  })
}

export function useRenameRoute() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: RotaAtualizar }) => renameRoute(id, body),
    onSuccess: (route) => {
      queryClient.setQueryData(['routes', 'detail', route.id], route)
      void queryClient.invalidateQueries({ queryKey: ['routes', 'all'] })
    },
  })
}

export function useSetRouteStops() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, parada_ids }: { id: number; parada_ids: number[] }) => setRouteStops(id, { parada_ids }),
    onSuccess: (route) => {
      queryClient.setQueryData(['routes', 'detail', route.id], route)
      void queryClient.invalidateQueries({ queryKey: ['routes', 'all'] })
    },
  })
}

export function useDeleteRoute() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteRoute(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['routes', 'all'] }),
  })
}
