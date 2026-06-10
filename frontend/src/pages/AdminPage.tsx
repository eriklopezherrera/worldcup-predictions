import { useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Check, Loader2, ShieldCheck } from 'lucide-react'
import { format } from 'date-fns'
import { useTournaments } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { useCurrentUser } from '../hooks/useUser'
import { useSetMatchResult } from '../hooks/useAdmin'
import type { Match } from '../types'

type Filter = 'to_score' | 'finished' | 'all'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'to_score', label: 'To score' },
  { key: 'finished', label: 'Finished' },
  { key: 'all', label: 'All' },
]

export default function AdminPage() {
  const { data: currentUser, isLoading: userLoading } = useCurrentUser()
  const { data: tournaments = [] } = useTournaments()

  const [selectedTournamentId, setSelectedTournamentId] = useState<string>()
  const [filter, setFilter] = useState<Filter>('to_score')

  const tournamentId = selectedTournamentId ?? tournaments[0]?.id
  const { data: matches = [], isLoading: matchesLoading } = useMatches(tournamentId)

  const visibleMatches = useMemo(() => {
    const now = new Date()
    switch (filter) {
      case 'to_score':
        // Kicked off but no final score entered yet
        return matches.filter(
          m => m.status !== 'finished' && new Date(m.kickoff_utc) <= now,
        )
      case 'finished':
        return matches.filter(m => m.status === 'finished')
      default:
        return matches
    }
  }, [matches, filter])

  if (userLoading) {
    return <div className="text-center py-20 text-gray-400">Loading…</div>
  }
  if (!currentUser?.is_admin) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      <div className="flex items-center gap-2 py-4">
        <ShieldCheck className="h-6 w-6 text-emerald-500" />
        <h1 className="text-2xl font-bold text-white">Admin — Match Results</h1>
      </div>

      {tournaments.length > 1 && (
        <select
          value={tournamentId ?? ''}
          onChange={e => setSelectedTournamentId(e.target.value)}
          className="mb-4 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
        >
          {tournaments.map(t => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.season})
            </option>
          ))}
        </select>
      )}

      <div className="mb-4 flex gap-2">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              filter === key
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {matchesLoading ? (
        <div className="text-center py-20 text-gray-400">Loading matches…</div>
      ) : visibleMatches.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          {filter === 'to_score'
            ? 'No matches waiting for a score.'
            : 'No matches found.'}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleMatches.map(match => (
            <AdminMatchRow key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  )
}

function AdminMatchRow({ match }: { match: Match }) {
  const [home, setHome] = useState(match.home_score ?? '')
  const [away, setAway] = useState(match.away_score ?? '')
  const { mutate, isPending, isSuccess, isError, error, data } = useSetMatchResult()

  const homeName = match.home_team?.name ?? 'TBD'
  const awayName = match.away_team?.name ?? 'TBD'
  const canSave = home !== '' && away !== '' && !isPending

  const save = () => {
    mutate({
      matchId: match.id,
      home_score: Number(home),
      away_score: Number(away),
    })
  }

  return (
    <div className="rounded-xl bg-gray-800 p-4">
      <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
        <span>{format(new Date(match.kickoff_utc), 'EEE d MMM, HH:mm')}</span>
        <span>
          {match.group_name ? `Group ${match.group_name}` : match.stage.replace(/_/g, ' ')}
          {match.status === 'finished' && (
            <span className="ml-2 text-emerald-400">finished</span>
          )}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span className="flex-1 truncate text-right text-sm font-medium text-white">
          {homeName}
        </span>
        <input
          type="number"
          min={0}
          max={99}
          value={home}
          onChange={e => setHome(e.target.value)}
          aria-label={`${homeName} score`}
          className="w-14 rounded-lg border border-gray-600 bg-gray-900 py-1.5 text-center text-white focus:border-emerald-500 focus:outline-none"
        />
        <span className="text-gray-500">–</span>
        <input
          type="number"
          min={0}
          max={99}
          value={away}
          onChange={e => setAway(e.target.value)}
          aria-label={`${awayName} score`}
          className="w-14 rounded-lg border border-gray-600 bg-gray-900 py-1.5 text-center text-white focus:border-emerald-500 focus:outline-none"
        />
        <span className="flex-1 truncate text-sm font-medium text-white">{awayName}</span>
        <button
          onClick={save}
          disabled={!canSave}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          Save
        </button>
      </div>

      {isSuccess && data && (
        <p className="mt-2 text-xs text-emerald-400">
          Saved — {data.predictions_scored} prediction
          {data.predictions_scored !== 1 ? 's' : ''} scored,{' '}
          {data.leaderboards_recomputed} leaderboard
          {data.leaderboards_recomputed !== 1 ? 's' : ''} updated.
        </p>
      )}
      {isError && (
        <p className="mt-2 text-xs text-red-400">
          Failed to save: {error instanceof Error ? error.message : 'unknown error'}
        </p>
      )}
    </div>
  )
}
