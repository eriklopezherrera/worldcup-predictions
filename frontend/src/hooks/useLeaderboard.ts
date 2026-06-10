import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { LeaderboardResponse } from '../types'

export function useGlobalLeaderboard(
  tournamentId: string | undefined,
  params?: { limit?: number; offset?: number },
) {
  return useQuery<LeaderboardResponse>({
    queryKey: ['leaderboard', 'global', tournamentId, params],
    queryFn: () =>
      api.get(`/tournaments/${tournamentId}/leaderboard`, { params }).then(r => r.data),
    enabled: !!tournamentId,
    staleTime: 2 * 60_000,
  })
}

export function usePartyLeaderboard(
  partyId: string | undefined,
  tournamentId: string | undefined,
) {
  return useQuery<LeaderboardResponse>({
    queryKey: ['leaderboard', 'party', partyId, tournamentId],
    queryFn: () =>
      api
        .get(`/parties/${partyId}/leaderboard`, { params: { tournament_id: tournamentId } })
        .then(r => r.data),
    enabled: !!partyId && !!tournamentId,
    staleTime: 2 * 60_000,
  })
}
