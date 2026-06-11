import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { LeaderboardResponse } from '../types'
import { useParties } from './useParties'

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
 * Tournament-wide leaderboard. Resolves to the tournament's global party (every
 * user is auto-joined to it) and reuses the party-leaderboard endpoint.
 */
export function useGlobalLeaderboard(tournamentId: string | undefined) {
  const { data: parties = [] } = useParties()
  const globalParty = parties.find((p) => p.is_global)
  return usePartyLeaderboard(globalParty?.id, tournamentId)
}
