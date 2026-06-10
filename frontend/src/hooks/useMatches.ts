import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { Match, MatchStage, MatchStatus } from '../types'

export interface MatchFilters {
  stage?: MatchStage
  status?: MatchStatus
  group?: string
}

export function useMatches(tournamentId: string | undefined, filters?: MatchFilters) {
  return useQuery<Match[]>({
    queryKey: ['matches', tournamentId, filters],
    queryFn: () =>
      api.get(`/tournaments/${tournamentId}/matches`, { params: filters }).then(r => r.data),
    enabled: !!tournamentId,
    staleTime: 60_000,
  })
}
