import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { meRequest } from '@/features/auth/api'
import { fetchAllPages } from '@/shared/api/pagination'
import type { components } from '@/shared/api/schema'
import { createUser, getSchool, listSchoolsLookup } from './api'

type UsuarioCriar = components['schemas']['UsuarioCriar']

export function useSchoolOptions() {
  return useQuery({
    queryKey: ['users', 'schools'],
    queryFn: () => fetchAllPages((limit, offset) => listSchoolsLookup({ limit, offset })),
  })
}

export function useSchool(id: number | null) {
  return useQuery({
    queryKey: ['users', 'school', id],
    queryFn: () => getSchool(id as number),
    enabled: id !== null,
  })
}

export function useMe() {
  return useQuery({
    queryKey: ['users', 'me'],
    queryFn: meRequest,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UsuarioCriar) => createUser(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'], refetchType: 'none' }),
  })
}
