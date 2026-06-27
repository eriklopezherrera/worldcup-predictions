import { useEffect, useMemo, useRef, useState } from 'react'
import { Star, Target, Trophy } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useTournaments } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { usePredictionSummary } from '../hooks/usePredictions'
import MatchCard from '../components/MatchCard'
import { TIME_FILTER_IDS, filterByTime, isUpcoming } from '../lib/matchFilters'
import type { TimeFilter } from '../lib/matchFilters'
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

const TAB_IDS: FilterTab[] = ['all', 'group', 'knockout', 'pending', 'scored']

export default function MyPredictionsPage() {
  const { t } = useTranslation()
  const { data: tournaments = [] } = useTournaments()
  const activeTournament = tournaments.find(t => t.status === 'active') ?? tournaments[0]

  const [selectedId, setSelectedId] = useState<string | undefined>(undefined)
  // 'group' is the fallback until the tournament loads; the server-configured
  // default (activeTournament.default_prediction_stage) is applied on first
  // load via the effect below, unless the user has already picked a tab.
  const [activeTab, setActiveTab] = useState<FilterTab>('group')
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('upcoming')
  const userPickedTab = useRef(false)

  useEffect(() => {
    if (!selectedId && activeTournament?.id) {
      setSelectedId(activeTournament.id)
    }
  }, [activeTournament?.id, selectedId])

  const handleTabClick = (tab: FilterTab) => {
    userPickedTab.current = true
    setActiveTab(tab)
  }

  const { data: matches = [], isLoading } = useMatches(selectedId)
  const { data: summary } = usePredictionSummary()

  // The knockout tab stays hidden until an admin opens at least one knockout
  // fixture for predictions, then it appears automatically.
  const knockoutOpen = useMemo(
    () => matches.some(m => KNOCKOUT_STAGES.includes(m.stage) && m.predictions_open),
    [matches],
  )
  const visibleTabs = useMemo(
    () => TAB_IDS.filter(id => id !== 'knockout' || knockoutOpen),
    [knockoutOpen],
  )

  // Seed the default tab from the active tournament once it resolves, but never
  // override a tab the user has manually selected.
  useEffect(() => {
    const preferred = activeTournament?.default_prediction_stage
    if (!userPickedTab.current && preferred) {
      // Don't land on a hidden knockout tab before any knockout stage is open.
      setActiveTab(preferred === 'knockout' && !knockoutOpen ? 'group' : preferred)
    }
  }, [activeTournament?.default_prediction_stage, knockoutOpen])

  // Stage tab first (group/knockout/pending/scored), then the time dimension.
  const stageMatches = useMemo<Match[]>(() => {
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

  const timeCounts = useMemo(() => {
    const upcoming = stageMatches.filter(isUpcoming).length
    return { upcoming, finished: stageMatches.length - upcoming, all: stageMatches.length }
  }, [stageMatches])

  const filteredMatches = useMemo<Match[]>(
    () => filterByTime(stageMatches, timeFilter),
    [stageMatches, timeFilter],
  )

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      <div className="py-4">
        <h1 className="text-2xl font-bold text-white">{t('predictions.title')}</h1>
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
            <div className="text-xs text-gray-400">{t('predictions.totalPoints')}</div>
          </div>
          <div className="bg-gray-800 rounded-xl p-3 text-center">
            <div className="flex justify-center mb-1">
              <Star size={14} className="text-yellow-400" />
            </div>
            <div className="text-lg font-bold text-yellow-400">{summary.exact_scores}</div>
            <div className="text-xs text-gray-400">{t('predictions.exactScores')}</div>
          </div>
          <div className="bg-gray-800 rounded-xl p-3 text-center">
            <div className="flex justify-center mb-1">
              <Target size={14} className="text-blue-400" />
            </div>
            <div className="text-lg font-bold text-emerald-400">{summary.predictions_made}</div>
            <div className="text-xs text-gray-400">{t('predictions.predicted')}</div>
          </div>
        </div>
      )}

      {/* Stage tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-2 scrollbar-none">
        {visibleTabs.map(id => (
          <button
            key={id}
            onClick={() => handleTabClick(id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0 ${
              activeTab === id
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {t(`predictions.tabs.${id}`)}
          </button>
        ))}
      </div>

      {/* Time filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-none">
        {TIME_FILTER_IDS.map(id => (
          <button
            key={id}
            onClick={() => setTimeFilter(id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0 ${
              timeFilter === id
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {t(`tournament.filters.${id}`)} {timeCounts[id]}
          </button>
        ))}
      </div>

      {/* Cards */}
      {isLoading ? (
        <div className="text-center py-20 text-gray-400">{t('predictions.loading')}</div>
      ) : filteredMatches.length === 0 ? (
        <div className="text-center py-20 text-gray-500">{t('predictions.noMatches')}</div>
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
