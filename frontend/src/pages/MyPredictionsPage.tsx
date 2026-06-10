import { useEffect, useMemo, useRef, useState } from 'react'
import { format } from 'date-fns'
import { Clock, Lock, Star, Target, Trophy } from 'lucide-react'
import { useTournaments } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { usePredictionSummary } from '../hooks/usePredictions'
import type { Match, MatchStage } from '../types'

type FilterTab = 'all' | 'group' | 'knockout' | 'pending' | 'scored'

const KNOCKOUT_STAGES: MatchStage[] = [
  'round_of_32',
  'round_of_16',
  'quarter_final',
  'semi_final',
  'third_place',
  'final',
]

const TABS: { id: FilterTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'group', label: 'Group Stage' },
  { id: 'knockout', label: 'Knockout' },
  { id: 'pending', label: 'Pending' },
  { id: 'scored', label: 'Scored' },
]

export default function MyPredictionsPage() {
  const { data: tournaments = [] } = useTournaments()
  const activeTournament = tournaments.find(t => t.status === 'active') ?? tournaments[0]

  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)
  // 'group' is the fallback until the tournament loads; the server-configured
  // default (activeTournament.default_prediction_stage) is applied on first
  // load via the effect below, unless the user has already picked a tab.
  const [activeTab, setActiveTab] = useState<FilterTab>('group')
  const userPickedTab = useRef(false)

  useEffect(() => {
    if (!selectedId && activeTournament?.id) {
      setSelectedId(activeTournament.id)
    }
  }, [activeTournament?.id, selectedId])

  // Seed the default tab from the active tournament once it resolves, but never
  // override a tab the user has manually selected.
  useEffect(() => {
    if (!userPickedTab.current && activeTournament?.default_prediction_stage) {
      setActiveTab(activeTournament.default_prediction_stage)
    }
  }, [activeTournament?.default_prediction_stage])

  const handleTabClick = (tab: FilterTab) => {
    userPickedTab.current = true
    setActiveTab(tab)
  }

  const { data: matches = [], isLoading } = useMatches(selectedId)
  const { data: summary } = usePredictionSummary()

  const filteredMatches = useMemo<Match[]>(() => {
    switch (activeTab) {
      case 'group':
        return matches.filter(m => m.stage === 'group_stage')
      case 'knockout':
        return matches.filter(m => KNOCKOUT_STAGES.includes(m.stage))
      case 'pending':
        return matches.filter(m => m.status === 'scheduled' && !m.prediction)
      case 'scored':
        return matches.filter(m => m.status === 'finished' && m.prediction != null)
      default:
        return matches
    }
  }, [matches, activeTab])

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      <div className="py-4">
        <h1 className="text-2xl font-bold text-white">My Predictions</h1>
      </div>

      {/* Tournament selector (only shown when multiple exist) */}
      {tournaments.length > 1 && (
        <div className="mb-4">
          <select
            value={selectedId ?? ''}
            onChange={e => setSelectedId(e.target.value)}
            className="w-full bg-gray-800 text-white rounded-lg px-3 py-2 text-sm border border-gray-700 focus:outline-none focus:border-emerald-500"
          >
            {tournaments.map(t => (
              <option key={t.id} value={t.id}>
                {t.name} {t.season ? `(${t.season})` : ''}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Summary stats */}
      {summary && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-gray-800 rounded-xl p-3 text-center">
            <div className="flex justify-center mb-1">
              <Trophy size={14} className="text-emerald-400" />
            </div>
            <div className="text-lg font-bold text-white">{summary.total_points}</div>
            <div className="text-xs text-gray-400">Total Points</div>
          </div>
          <div className="bg-gray-800 rounded-xl p-3 text-center">
            <div className="flex justify-center mb-1">
              <Star size={14} className="text-yellow-400" />
            </div>
            <div className="text-lg font-bold text-yellow-400">{summary.exact_scores}</div>
            <div className="text-xs text-gray-400">Exact Scores</div>
          </div>
          <div className="bg-gray-800 rounded-xl p-3 text-center">
            <div className="flex justify-center mb-1">
              <Target size={14} className="text-blue-400" />
            </div>
            <div className="text-lg font-bold text-emerald-400">{summary.predictions_made}</div>
            <div className="text-xs text-gray-400">Predicted</div>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-none">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0 ${
              activeTab === tab.id
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Cards */}
      {isLoading ? (
        <div className="text-center py-20 text-gray-400">Loading predictions…</div>
      ) : filteredMatches.length === 0 ? (
        <div className="text-center py-20 text-gray-500">No matches for this filter.</div>
      ) : (
        <div className="flex flex-col gap-3">
          {filteredMatches.map(match => (
            <PredictionCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  )
}

function PredictionCard({ match }: { match: Match }) {
  const pred = match.prediction
  const isScored = match.status === 'finished'
  const isPending = match.status === 'scheduled' && !pred
  const isLive = match.status === 'live'
  const isLocked = pred?.is_locked && match.status === 'scheduled'

  return (
    <div className="bg-gray-800 rounded-xl p-4">
      {/* Top row: date + status badge */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500">
          {format(new Date(match.kickoff_utc), 'EEE d MMM, HH:mm')}
        </span>
        <div className="flex items-center gap-1.5">
          {isLive && (
            <span className="text-xs text-red-400 font-bold animate-pulse">LIVE</span>
          )}
          {isPending && (
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <Clock size={10} />
              Pending
            </span>
          )}
          {isLocked && !isLive && (
            <span className="flex items-center gap-1 text-xs text-yellow-500">
              <Lock size={10} />
              Locked
            </span>
          )}
          {isScored && pred && <PointsBadge points={pred.total_points} />}
          {isScored && !pred && (
            <span className="text-xs text-gray-500">No prediction · 0 pts</span>
          )}
        </div>
      </div>

      {/* Teams row */}
      <div className="flex items-center gap-2">
        {/* Home */}
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {match.home_team?.logo_url && (
            <img
              src={match.home_team.logo_url}
              alt=""
              className="w-6 h-6 object-contain flex-shrink-0"
            />
          )}
          <span className="text-sm text-white font-medium truncate">
            {match.home_team?.name ?? 'TBD'}
          </span>
        </div>

        {/* Score column */}
        <div className="text-center px-2 flex-shrink-0">
          {isScored ? (
            <div className="text-white font-bold tabular-nums">
              {match.home_score}–{match.away_score}
            </div>
          ) : (
            <div className="text-gray-500 text-xs">vs</div>
          )}
          {pred && (
            <div className="text-gray-500 text-xs mt-0.5 tabular-nums">
              {pred.predicted_home_score}–{pred.predicted_away_score}
            </div>
          )}
        </div>

        {/* Away */}
        <div className="flex items-center gap-2 flex-1 min-w-0 justify-end">
          <span className="text-sm text-white font-medium truncate text-right">
            {match.away_team?.name ?? 'TBD'}
          </span>
          {match.away_team?.logo_url && (
            <img
              src={match.away_team.logo_url}
              alt=""
              className="w-6 h-6 object-contain flex-shrink-0"
            />
          )}
        </div>
      </div>
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
