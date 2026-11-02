import { keepPreviousData, useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import { useAuth } from '@/shared/auth/useAuth'
import {
  createClass,
  deleteClass,
  getClass,
  getStudent,
  listActiveEnrollments,
  listClasses,
  listSchoolsLookup,
  updateClass,
} from './api'

type TurmaCriar = components['schemas']['TurmaCriar']

type PageParams = { limit: number; offset: number }

export function useClasses(pager: PageParams, escolaId?: number) {
  return useQuery({
    queryKey: ['classes', 'list', pager.limit, pager.offset, escolaId ?? null],
    queryFn: () => listClasses({ limit: pager.limit, offset: pager.offset, escola_id: escolaId }),
    placeholderData: keepPreviousData,
  })
}

export function useClassesInScope() {
  const { role, user } = useAuth()
  const escolaId = role === 'diretor' ? (user?.escola_id ?? undefined) : undefined
  return useQuery({
    queryKey: ['classes', 'scope', escolaId ?? null],
    queryFn: () => fetchAllPages((limit, offset) => listClasses({ limit, offset, escola_id: escolaId })),
  })
}

export function useClassName(id: number): string {
  const classes = useClassesInScope()
  return classes.data?.find((turma) => turma.id === id)?.nome ?? '—'
}

export function useSchoolOptions() {
  return useQuery({
    queryKey: ['classes', 'schools'],
    queryFn: () => fetchAllPages((limit, offset) => listSchoolsLookup({ limit, offset })),
  })
}

export function useClass(id: number) {
  return useQuery({
    queryKey: ['classes', 'detail', id],
    queryFn: () => getClass(id),
  })
}

export function useActiveEnrollments(turmaId: number) {
  return useQuery({
    queryKey: ['classes', 'enrollments', turmaId],
    queryFn: () => fetchAllPages((limit, offset) => listActiveEnrollments(turmaId, { limit, offset })),
  })
}

export function useStudentsById(ids: number[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ['students', id],
      queryFn: () => getStudent(id),
    })),
  })
}

export function useSaveClass(id?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: TurmaCriar) => (id === undefined ? createClass(body) : updateClass(id, body)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['classes'], refetchType: 'none' }),
  })
}

export function useDeleteClass() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteClass(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['classes'], refetchType: 'none' }),
  })
}
