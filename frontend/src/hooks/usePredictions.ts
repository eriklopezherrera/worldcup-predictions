import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/apiClient'
import type { Match, Prediction, PredictionSummary } from '../types'

interface PredictionFilters {
  tournament_id?: string
  status?: string
}

interface SavePredictionArgs {
  matchId: string
  tournamentId: string
  home: number
  away: number
}

export function usePredictions(filters?: PredictionFilters) {
  return useQuery<Prediction[]>({
    queryKey: ['predictions', filters],
    queryFn: () => api.get('/predictions', { params: filters }).then(r => r.data),
    staleTime: 60_000,
  })
}

export function usePredictionSummary() {
  return useQuery<PredictionSummary>({
    queryKey: ['predictions', 'summary'],
    queryFn: () => api.get('/predictions/summary').then(r => r.data),
    staleTime: 60_000,
  })
}

export function useSavePrediction() {
  const queryClient = useQueryClient()

  return useMutation<Prediction, Error, SavePredictionArgs, { snapshot: Match[] | undefined }>({
    mutationFn: ({ matchId, home, away }) =>
      api
        .put<Prediction>(`/predictions/${matchId}`, {
          predicted_home_score: home,
          predicted_away_score: away,
        })
        .then(r => r.data),

    onMutate: async ({ matchId, tournamentId, home, away }) => {
      await queryClient.cancelQueries({ queryKey: ['matches', tournamentId] })
      const snapshot = queryClient.getQueryData<Match[]>(['matches', tournamentId])
      queryClient.setQueryData<Match[]>(['matches', tournamentId], old =>
        old?.map(m =>
          m.id === matchId
            ? {
                ...m,
                prediction: {
                  id: m.prediction?.id ?? 'optimistic',
                  match_id: matchId,
                  predicted_home_score: home,
                  predicted_away_score: away,
                  points_result: m.prediction?.points_result ?? 0,
                  points_exact: m.prediction?.points_exact ?? 0,
                  total_points: m.prediction?.total_points ?? 0,
                  is_locked: m.prediction?.is_locked ?? false,
                },
              }
            : m,
        ) ?? [],
      )
      return { snapshot }
    },

    onError: (_err, { tournamentId }, ctx) => {
      if (ctx?.snapshot !== undefined) {
        queryClient.setQueryData(['matches', tournamentId], ctx.snapshot)
      }
    },

    onSettled: (_data, _err, { tournamentId }) => {
      queryClient.invalidateQueries({ queryKey: ['matches', tournamentId] })
      queryClient.invalidateQueries({ queryKey: ['predictions', 'summary'] })
    },
  })
}
