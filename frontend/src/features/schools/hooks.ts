import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import {
  createSchool,
  deleteSchool,
  getSchool,
  listClassAttendance,
  listClassesBySchool,
  listPolesLookup,
  listSchools,
  listTeachersBySchool,
  updateSchool,
} from './api'

type EscolaCriar = components['schemas']['EscolaCriar']

type PageParams = { limit: number; offset: number }

export function useSchools(pager: PageParams, poloId?: number) {
  return useQuery({
    queryKey: ['schools', 'list', pager.limit, pager.offset, poloId ?? null],
    queryFn: () => listSchools({ limit: pager.limit, offset: pager.offset, polo_id: poloId }),
    placeholderData: keepPreviousData,
  })
}

export function useAllSchools() {
  return useQuery({
    queryKey: ['schools', 'all'],
    queryFn: () => fetchAllPages((limit, offset) => listSchools({ limit, offset })),
  })
}

export function usePoleOptions() {
  return useQuery({
    queryKey: ['schools', 'poles-lookup'],
    queryFn: () => fetchAllPages((limit, offset) => listPolesLookup({ limit, offset })),
  })
}

export function useSchool(id: number) {
  return useQuery({
    queryKey: ['schools', 'detail', id],
    queryFn: () => getSchool(id),
  })
}

export function useSchoolClasses(id: number) {
  return useQuery({
    queryKey: ['schools', 'classes', id],
    queryFn: () => fetchAllPages((limit, offset) => listClassesBySchool(id, { limit, offset })),
  })
}

export function useSchoolTeachers(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ['schools', 'teachers', id],
    queryFn: () => fetchAllPages((limit, offset) => listTeachersBySchool(id, { limit, offset })),
    enabled,
  })
}

export function useClassAttendance(dataInicio: string, dataFim: string, enabled: boolean) {
  return useQuery({
    queryKey: ['schools', 'attendance', 'turma', dataInicio, dataFim],
    queryFn: () => listClassAttendance({ data_inicio: dataInicio, data_fim: dataFim }),
    enabled,
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
