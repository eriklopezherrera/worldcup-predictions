import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { PublicPrediction, PublicUser, User } from '../types'

export function useCurrentUser() {
  return useQuery<User>({
    queryKey: ['users', 'me'],
    queryFn: () => api.get('/users/me').then(r => r.data),
    staleTime: 10 * 60_000,
  })
}

/** Public profile (no email) of any user by id. */
export function usePublicUser(userId: string | undefined) {
  return useQuery<PublicUser>({
    queryKey: ['users', userId],
    queryFn: () => api.get(`/users/${userId}`).then(r => r.data),
    enabled: !!userId,
    staleTime: 10 * 60_000,
  })
}

/** Another player's already-scored predictions, optionally for one tournament. */
export function usePublicUserPredictions(
  userId: string | undefined,
  tournamentId?: string,
) {
  return useQuery<PublicPrediction[]>({
    queryKey: ['users', userId, 'predictions', tournamentId],
    queryFn: () =>
      api
        .get(`/users/${userId}/predictions`, {
          params: tournamentId ? { tournament_id: tournamentId } : undefined,
        })
        .then(r => r.data),
    enabled: !!userId,
    staleTime: 60_000,
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
