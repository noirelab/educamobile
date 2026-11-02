import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from '@/shared/api/schema'
import { createStudent, deleteStudent, getStudent, listStopOptions, listStudents, updateStudent } from './api'

type EstudanteCadastrar = components['schemas']['EstudanteCadastrar']

type PageParams = { limit: number; offset: number }

export function useStudents(pager: PageParams) {
  return useQuery({
    queryKey: ['students', 'list', pager.limit, pager.offset],
    queryFn: () => listStudents({ limit: pager.limit, offset: pager.offset }),
    placeholderData: keepPreviousData,
  })
}

export function useStudent(id: number) {
  return useQuery({
    queryKey: ['students', 'detail', id],
    queryFn: () => getStudent(id),
  })
}

export function useStopOptions(enabled = true) {
  return useQuery({
    queryKey: ['students', 'stop-options'],
    queryFn: () => listStopOptions(),
    enabled,
  })
}

export function useSaveStudent(id?: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: EstudanteCadastrar) => (id === undefined ? createStudent(body) : updateStudent(id, body)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['students'] }),
  })
}

export function useDeleteStudent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteStudent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['students'] }),
  })
}
