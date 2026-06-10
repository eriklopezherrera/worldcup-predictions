import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { Tournament } from '../types'

export function useTournaments() {
  return useQuery<Tournament[]>({
    queryKey: ['tournaments'],
    queryFn: () => api.get('/tournaments').then(r => r.data),
    staleTime: 5 * 60_000,
  })
}

export function useTournament(id: string | undefined) {
  return useQuery<Tournament>({
    queryKey: ['tournaments', id],
    queryFn: () => api.get(`/tournaments/${id}`).then(r => r.data),
    enabled: !!id,
    staleTime: 5 * 60_000,
  })
}
