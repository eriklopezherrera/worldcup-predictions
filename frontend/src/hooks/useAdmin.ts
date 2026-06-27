import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { Match, MatchStage } from '../types'

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

export interface UpdateMatchArgs {
  matchId: string
  /** ISO UTC string, omit to leave unchanged. */
  kickoff_utc?: string
  /** Pass set_home_team:true with home_team_id (null clears to TBD). */
  home_team_id?: string | null
  away_team_id?: string | null
  set_home_team?: boolean
  set_away_team?: boolean
}

export function useUpdateMatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ matchId, ...body }: UpdateMatchArgs) =>
      api.put<Match>(`/admin/matches/${matchId}`, body).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    },
  })
}

export interface SetStageOpenArgs {
  tournamentId: string
  stage: MatchStage
  predictions_open: boolean
}

export interface StagePredictionsResponse {
  stage: string
  predictions_open: boolean
  matches_updated: number
}

export function useSetStageOpen() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ tournamentId, stage, predictions_open }: SetStageOpenArgs) =>
      api
        .put<StagePredictionsResponse>(
          `/admin/tournaments/${tournamentId}/stages/${stage}`,
          { predictions_open },
        )
        .then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    },
  })
}
