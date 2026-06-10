import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { User } from '../types'

export function useCurrentUser() {
  return useQuery<User>({
    queryKey: ['users', 'me'],
    queryFn: () => api.get('/users/me').then(r => r.data),
    staleTime: 10 * 60_000,
  })
}

interface UpdateUserArgs {
  display_name?: string | null
  avatar_url?: string | null
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: UpdateUserArgs) =>
      api.patch<User>('/users/me', body).then(r => r.data),
    onSuccess: (user) => {
      queryClient.setQueryData(['users', 'me'], user)
    },
  })
}
