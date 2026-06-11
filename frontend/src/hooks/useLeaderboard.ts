import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { LeaderboardResponse } from '../types'

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

/**
 * Tournament-wide leaderboard. The backend resolves the tournament's global
 * party server-side, so this works regardless of the caller's party membership.
 */
export function useGlobalLeaderboard(tournamentId: string | undefined) {
  return useQuery<LeaderboardResponse>({
    queryKey: ['leaderboard', 'global', tournamentId],
    queryFn: () =>
      api.get(`/tournaments/${tournamentId}/leaderboard`).then(r => r.data),
    enabled: !!tournamentId,
    staleTime: 2 * 60_000,
  })
}
