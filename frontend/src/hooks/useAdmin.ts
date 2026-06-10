import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/apiClient'

export interface MatchResultArgs {
  matchId: string
  home_score: number
  away_score: number
}

export interface MatchResultResponse {
  match_id: string
  home_score: number
  away_score: number
  status: string
  predictions_scored: number
  leaderboards_recomputed: number
}

export function useSetMatchResult() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ matchId, home_score, away_score }: MatchResultArgs) =>
      api
        .put<MatchResultResponse>(`/admin/matches/${matchId}/result`, {
          home_score,
          away_score,
        })
        .then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] })
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
    },
  })
}
