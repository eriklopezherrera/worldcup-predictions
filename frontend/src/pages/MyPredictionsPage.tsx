import { useEffect, useMemo, useRef, useState } from 'react'
import { Star, Target, Trophy } from 'lucide-react'
import { useTournaments } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { usePredictionSummary } from '../hooks/usePredictions'
import MatchCard from '../components/MatchCard'
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
            <MatchCard key={match.id} match={match} tournamentId={selectedId!} />
          ))}
        </div>
      )}
    </div>
  )
}
