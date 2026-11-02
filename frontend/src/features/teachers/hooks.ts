import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import {
  createTeacher,
  deleteTeacher,
  getTeacher,
  listSchoolsLookup,
  listTeachers,
  updateTeacher,
} from './api'

type ProfessorCriar = components['schemas']['ProfessorCriar']

type PageParams = { limit: number; offset: number }

export function useTeachers(pager: PageParams, escolaId?: number) {
  return useQuery({
    queryKey: ['teachers', 'list', pager.limit, pager.offset, escolaId ?? null],
    queryFn: () => listTeachers({ limit: pager.limit, offset: pager.offset, escola_id: escolaId }),
    placeholderData: keepPreviousData,
  })
}

export function useSchoolOptions() {
  return useQuery({
    queryKey: ['teachers', 'schools'],
    queryFn: () => fetchAllPages((limit, offset) => listSchoolsLookup({ limit, offset })),
  })
}

export function useTeacher(id: number) {
  return useQuery({
    queryKey: ['teachers', 'detail', id],
    queryFn: () => getTeacher(id),
  })
}

export function useSaveTeacher(id?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ProfessorCriar) => (id === undefined ? createTeacher(body) : updateTeacher(id, body)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['teachers'], refetchType: 'none' }),
  })
}

export function useDeleteTeacher() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteTeacher(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['teachers'], refetchType: 'none' }),
  })
}
