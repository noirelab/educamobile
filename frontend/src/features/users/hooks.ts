import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { meRequest } from '@/features/auth/api'
import type { components } from '@/shared/api/schema'
import { changePassword, createUser } from './api'

type UsuarioCriar = components['schemas']['UsuarioCriar']

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

export function useChangePassword() {
  return useMutation({ mutationFn: changePassword })
}
