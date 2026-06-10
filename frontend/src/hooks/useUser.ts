import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { User } from '../types'

export function useCurrentUser() {
  return useQuery<User>({
    queryKey: ['users', 'me'],
    queryFn: () => api.get('/users/me').then(r => r.data),
    staleTime: 10 * 60_000,
  })
}
