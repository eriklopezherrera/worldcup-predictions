import { useQuery } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { Match, Prediction } from '../types'
import type { MatchStage, MatchStatus } from '../types'

export interface MatchFilters {
  stage?: MatchStage
  status?: MatchStatus
  group?: string
}

// The API returns the caller's pick as `my_prediction` (without match_id /
// is_locked, which live at the match level). The rest of the app reads
// `match.prediction`, so we normalize here at the single fetch boundary.
type RawPrediction = Omit<Prediction, 'match_id' | 'is_locked'>
type RawMatch = Omit<Match, 'prediction'> & { my_prediction?: RawPrediction | null }

function normalizeMatch({ my_prediction, ...m }: RawMatch): Match {
  return {
    ...m,
    prediction: my_prediction
      ? { ...my_prediction, match_id: m.id, is_locked: m.is_locked ?? false }
      : null,
  }
}

export function useMatches(tournamentId: string | undefined, filters?: MatchFilters) {
  return useQuery<Match[]>({
    queryKey: ['matches', tournamentId, filters],
    queryFn: () =>
      api
        .get<RawMatch[]>(`/tournaments/${tournamentId}/matches`, { params: filters })
        .then(r => r.data.map(normalizeMatch)),
    enabled: !!tournamentId,
    staleTime: 60_000,
  })
}
