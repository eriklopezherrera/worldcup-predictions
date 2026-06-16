import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ChevronDown, ChevronRight, Star, Target, TrendingUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useTournament } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { usePredictionSummary } from '../hooks/usePredictions'
import { useGlobalLeaderboard } from '../hooks/useLeaderboard'
import { useCurrentUser } from '../hooks/useUser'
import MatchCard from '../components/MatchCard'
import { TIME_FILTER_IDS, filterByTime, isUpcoming } from '../lib/matchFilters'
import type { TimeFilter } from '../lib/matchFilters'
import type { Match, MatchStage } from '../types'

const STAGE_ORDER: MatchStage[] = [
  'group_stage',
  'round_of_32',
  'round_of_16',
  'quarter_final',
  'semi_final',
  'third_place',
  'final',
]

interface Section {
  key: string
  label: string
  matches: Match[]
}

export default function TournamentPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const { data: tournament } = useTournament(id)
  const { data: matches = [], isLoading } = useMatches(id)
  const { data: summary } = usePredictionSummary()
  const { data: leaderboard } = useGlobalLeaderboard(id)
  const { data: currentUser } = useCurrentUser()

  const [openSections, setOpenSections] = useState<Record<string, boolean>>({})
  const [filter, setFilter] = useState<TimeFilter>('upcoming')

  const userRank = useMemo(() => {
    if (!leaderboard || !currentUser) return null
    return leaderboard.entries.find(e => e.user_id === currentUser.id)?.rank ?? null
  }, [leaderboard, currentUser])

  const filterCounts = useMemo(() => {
    const upcoming = matches.filter(isUpcoming).length
    return { upcoming, finished: matches.length - upcoming, all: matches.length }
  }, [matches])

  const visibleMatches = useMemo<Match[]>(() => filterByTime(matches, filter), [matches, filter])

  const sections = useMemo<Section[]>(() => {
    const map = new Map<string, Section>()

    for (const match of visibleMatches) {
      const sectionKey =
        match.stage === 'group_stage' && match.match_day != null
          ? `${match.stage}-day-${match.match_day}`
          : match.stage

      if (!map.has(sectionKey)) {
        const dayLabel =
          match.stage === 'group_stage' && match.match_day != null
            ? t('tournament.matchday', { day: match.match_day })
            : ''
        map.set(sectionKey, {
          key: sectionKey,
          label: t(`stages.${match.stage}`) + dayLabel,
          matches: [],
        })
      }
      map.get(sectionKey)!.matches.push(match)
    }

    // Sort sections by stage order, then by matchday
    return [...map.values()].sort((a, b) => {
      const aStage = a.matches[0].stage
      const bStage = b.matches[0].stage
      const stageDiff = STAGE_ORDER.indexOf(aStage) - STAGE_ORDER.indexOf(bStage)
      if (stageDiff !== 0) return stageDiff
      return (a.matches[0].match_day ?? 0) - (b.matches[0].match_day ?? 0)
    })
  }, [visibleMatches, t])

  const toggleSection = (key: string) => {
    setOpenSections(prev => ({ ...prev, [key]: !(prev[key] ?? true) }))
  }

  const isSectionOpen = (key: string) => openSections[key] ?? true

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      {/* Header */}
      <div className="py-4">
        <h1 className="text-2xl font-bold text-white">
          {tournament?.name ?? t('tournament.fallbackTitle')}
        </h1>
        {tournament?.season && (
          <p className="text-sm text-gray-400 mt-0.5">{tournament.season}</p>
        )}
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <StatCard
          icon={<Target size={14} className="text-emerald-400" />}
          value={`${summary?.predictions_made ?? 0}/${matches.length}`}
          label={t('tournament.predictions')}
        />
        <StatCard
          icon={<Star size={14} className="text-yellow-400" />}
          value={summary?.total_points ?? 0}
          label={t('tournament.points')}
        />
        <StatCard
          icon={<TrendingUp size={14} className="text-blue-400" />}
          value={userRank != null ? `#${userRank}` : '—'}
          label={t('tournament.globalRank')}
        />
      </div>

      {/* Filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-none">
        {TIME_FILTER_IDS.map(id => (
          <button
            key={id}
            onClick={() => setFilter(id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0 ${
              filter === id
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            {t(`tournament.filters.${id}`)} {filterCounts[id]}
          </button>
        ))}
      </div>

      {/* Match sections */}
      {isLoading ? (
        <div className="text-center py-20 text-gray-400">{t('tournament.loadingMatches')}</div>
      ) : sections.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          {filter === 'upcoming' ? t('tournament.noUpcoming') : t('tournament.noMatches')}
        </div>
      ) : (
        sections.map(section => (
          <div key={section.key} className="mb-4">
            <button
              onClick={() => toggleSection(section.key)}
              className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 rounded-xl text-left hover:bg-gray-700/60 transition-colors"
            >
              <span className="font-semibold text-white text-sm">{section.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">
                  {t('tournament.matchCount', { count: section.matches.length })}
                </span>
                {isSectionOpen(section.key) ? (
                  <ChevronDown size={16} className="text-gray-400" />
                ) : (
                  <ChevronRight size={16} className="text-gray-400" />
                )}
              </div>
            </button>

            {isSectionOpen(section.key) && (
              <div className="mt-2 flex flex-col gap-3">
                {section.matches.map(match => (
                  <MatchCard key={match.id} match={match} tournamentId={id!} />
                ))}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

function StatCard({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode
  value: string | number
  label: string
}) {
  return (
    <div className="bg-gray-800 rounded-xl p-3 text-center">
      <div className="flex items-center justify-center mb-1">{icon}</div>
      <div className="text-lg font-bold text-white">{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  )
}
