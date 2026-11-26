import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import {
  createSchool,
  deleteSchool,
  getSchool,
  listSchools,
  updateSchool,
} from './api'

type EscolaCriar = components['schemas']['EscolaCriar']

type PageParams = { limit: number; offset: number }

export function useSchools(pager: PageParams) {
  return useQuery({
    queryKey: ['schools', 'list', pager.limit, pager.offset],
    queryFn: () => listSchools({ limit: pager.limit, offset: pager.offset }),
    placeholderData: keepPreviousData,
  })
}

export function useAllSchools() {
  return useQuery({
    queryKey: ['schools', 'all'],
    queryFn: () => fetchAllPages((limit, offset) => listSchools({ limit, offset })),
  })
}

export function useSchool(id: number) {
  return useQuery({
    queryKey: ['schools', 'detail', id],
    queryFn: () => getSchool(id),
  })
}

export function useSaveSchool(id?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: EscolaCriar) => (id === undefined ? createSchool(body) : updateSchool(id, body)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schools'], refetchType: 'none' }),
  })
}

export function useDeleteSchool() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteSchool(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['schools'], refetchType: 'none' }),
  })
}
