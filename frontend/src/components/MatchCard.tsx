import { useEffect, useState } from 'react'
import { Loader2, Lock, Wifi } from 'lucide-react'
import { format } from 'date-fns'
import ScoreInput from './ScoreInput'
import Countdown from './Countdown'
import { useSavePrediction } from '../hooks/usePredictions'
import type { Match } from '../types'

interface MatchCardProps {
  match: Match
  tournamentId: string
}

function TeamDisplay({ name, logoUrl }: { name: string; logoUrl?: string | null }) {
  return (
    <div className="flex flex-col items-center gap-1.5 w-20">
      {logoUrl ? (
        <img src={logoUrl} alt={name} className="w-9 h-9 object-contain" />
      ) : (
        <div className="w-9 h-9 rounded-full bg-gray-600 flex items-center justify-center text-xs font-bold text-white">
          {name.slice(0, 2).toUpperCase()}
        </div>
      )}
      <span className="text-xs text-gray-300 text-center leading-tight line-clamp-2">{name}</span>
    </div>
  )
}

function PointsBadge({ points }: { points: number }) {
  const cls =
    points === 5
      ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
      : points >= 2
        ? 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30'
        : 'text-gray-400 bg-gray-700 border-gray-600'
  return (
    <span className={`inline-block px-2 py-0.5 rounded border text-xs font-bold ${cls}`}>
      {points > 0 ? `+${points}` : '0'} pts
    </span>
  )
}

function MatchStatusBadge({ status }: { status: Match['status'] }) {
  if (status === 'live') {
    return (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs font-bold animate-pulse">
        <Wifi size={10} />
        LIVE
      </span>
    )
  }
  if (status === 'postponed') {
    return (
      <span className="px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 text-xs font-medium">
        Postponed
      </span>
    )
  }
  if (status === 'cancelled') {
    return (
      <span className="px-2 py-0.5 rounded-full bg-gray-700 text-gray-400 text-xs font-medium">
        Cancelled
      </span>
    )
  }
  return null
}

export default function MatchCard({ match, tournamentId }: MatchCardProps) {
  const isMatchLocked =
    match.prediction?.is_locked ||
    match.status !== 'scheduled' ||
    new Date(match.kickoff_utc) <= new Date()

  const [homeVal, setHomeVal] = useState(match.prediction?.predicted_home_score ?? 0)
  const [awayVal, setAwayVal] = useState(match.prediction?.predicted_away_score ?? 0)

  // Sync local state when prediction is updated from cache
  useEffect(() => {
    if (match.prediction) {
      setHomeVal(match.prediction.predicted_home_score)
      setAwayVal(match.prediction.predicted_away_score)
    }
  }, [match.prediction?.predicted_home_score, match.prediction?.predicted_away_score])

  const { mutate: save, isPending, isError, reset } = useSavePrediction()

  const hasChanges =
    !match.prediction ||
    homeVal !== match.prediction.predicted_home_score ||
    awayVal !== match.prediction.predicted_away_score

  const handleSave = () => {
    reset()
    save({ matchId: match.id, tournamentId, home: homeVal, away: awayVal })
  }

  return (
    <div className="bg-gray-800 rounded-xl p-4 transition-all duration-300">
      {/* Row: kickoff time + status badge */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500">
          {format(new Date(match.kickoff_utc), 'EEE d MMM, HH:mm')}
          {match.venue ? ` · ${match.venue}` : ''}
        </span>
        <MatchStatusBadge status={match.status} />
        {match.status === 'scheduled' && isMatchLocked && (
          <span className="flex items-center gap-1 text-xs text-yellow-500">
            <Lock size={10} />
            Locked
          </span>
        )}
      </div>

      {/* Teams + score area */}
      <div className="flex items-center justify-between gap-2">
        <TeamDisplay name={match.home_team.name} logoUrl={match.home_team.logo_url} />

        <div className="flex-1 flex items-center justify-center">
          {match.status === 'finished' ? (
            <FinishedScore match={match} />
          ) : match.status === 'live' ? (
            <LiveScore match={match} />
          ) : isMatchLocked ? (
            <LockedScore match={match} />
          ) : (
            <div className="flex items-center gap-2">
              <ScoreInput value={homeVal} onChange={setHomeVal} />
              <span className="text-gray-500 font-bold text-lg">–</span>
              <ScoreInput value={awayVal} onChange={setAwayVal} />
            </div>
          )}
        </div>

        <TeamDisplay name={match.away_team.name} logoUrl={match.away_team.logo_url} />
      </div>

      {/* Footer: countdown + save (editable only) */}
      {!isMatchLocked && match.status === 'scheduled' && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700">
          <Countdown kickoffUtc={match.kickoff_utc} />
          <div className="flex items-center gap-2">
            {isError && (
              <span className="text-red-400 text-xs">Failed to save</span>
            )}
            <button
              onClick={handleSave}
              disabled={!hasChanges || isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {isPending && <Loader2 size={12} className="animate-spin" />}
              {match.prediction ? 'Update' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function FinishedScore({ match }: { match: Match }) {
  const pred = match.prediction
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-white tabular-nums">
        {match.home_score} – {match.away_score}
      </div>
      {pred ? (
        <>
          <div className="text-xs text-gray-500 mt-1">
            Your pick: {pred.predicted_home_score}–{pred.predicted_away_score}
          </div>
          <div className="mt-1.5">
            <PointsBadge points={pred.total_points} />
          </div>
        </>
      ) : (
        <div className="text-xs text-gray-500 mt-1">No prediction · 0 pts</div>
      )}
    </div>
  )
}

function LiveScore({ match }: { match: Match }) {
  const pred = match.prediction
  return (
    <div className="text-center">
      {match.home_score != null ? (
        <div className="text-2xl font-bold text-white tabular-nums">
          {match.home_score} – {match.away_score}
          {match.home_score_ht != null && (
            <span className="text-xs text-gray-500 font-normal ml-1">
              (HT {match.home_score_ht}–{match.away_score_ht})
            </span>
          )}
        </div>
      ) : (
        <div className="text-gray-400 text-sm">In Progress</div>
      )}
      {pred && (
        <div className="text-xs text-gray-500 mt-1 opacity-60">
          Your pick: {pred.predicted_home_score}–{pred.predicted_away_score}
        </div>
      )}
    </div>
  )
}

function LockedScore({ match }: { match: Match }) {
  const pred = match.prediction
  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-1 text-gray-500 text-xs mb-1.5">
        <Lock size={11} />
        <span>Prediction locked</span>
      </div>
      {pred ? (
        <div className="text-xl font-bold text-gray-400 tabular-nums">
          {pred.predicted_home_score} – {pred.predicted_away_score}
        </div>
      ) : (
        <div className="text-sm text-gray-500">No prediction made</div>
      )}
    </div>
  )
}
