import { useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ArrowLeft, Check, Loader2, ShieldCheck } from 'lucide-react'
import { format } from 'date-fns'
import { useTranslation } from 'react-i18next'
import { useTournaments } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { useCurrentUser } from '../hooks/useUser'
import { useSetMatchResult } from '../hooks/useAdmin'
import { useDateLocale } from '../i18n/useDateLocale'
import { localizeTeamName } from '../i18n/teams'
import type { Match } from '../types'

type Filter = 'to_score' | 'finished' | 'all'

const FILTER_KEYS: Filter[] = ['to_score', 'finished', 'all']

export default function AdminScoringPage() {
  const { t } = useTranslation()
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
    return <div className="text-center py-20 text-gray-400">{t('admin.loading')}</div>
  }
  if (!currentUser?.is_admin) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      <Link
        to="/admin"
        className="inline-flex items-center gap-1.5 pt-4 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('admin.backToHub')}
      </Link>

      <div className="flex items-center gap-2 py-4">
        <ShieldCheck className="h-6 w-6 text-emerald-500" />
        <h1 className="text-2xl font-bold text-white">{t('admin.scoring.title')}</h1>
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
        {FILTER_KEYS.map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
              filter === key
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            {t(`admin.filters.${key}`)}
          </button>
        ))}
      </div>

      {matchesLoading ? (
        <div className="text-center py-20 text-gray-400">{t('admin.loadingMatches')}</div>
      ) : visibleMatches.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          {filter === 'to_score'
            ? t('admin.noneToScore')
            : t('admin.noneFound')}
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

const DECIDED_BY_OPTIONS = ['regulation', 'extra_time', 'penalties'] as const

function AdminMatchRow({ match }: { match: Match }) {
  const { t, i18n } = useTranslation()
  const dateLocale = useDateLocale()
  const [home, setHome] = useState(match.home_score ?? '')
  const [away, setAway] = useState(match.away_score ?? '')
  const [drawWinnerId, setDrawWinnerId] = useState<string | null>(match.winner_team_id ?? null)
  const [decidedBy, setDecidedBy] = useState<string>(match.decided_by ?? '')
  const { mutate, isPending, isSuccess, isError, error, data } = useSetMatchResult()

  const homeName = localizeTeamName(match.home_team?.name, i18n.language) || t('common.tbd')
  const awayName = localizeTeamName(match.away_team?.name, i18n.language) || t('common.tbd')

  const isKnockout = match.stage !== 'group_stage'
  const scoresEntered = home !== '' && away !== ''
  const isDraw = scoresEntered && Number(home) === Number(away)
  // Decisive scores imply the winner; only a draw (penalties) needs a manual pick.
  const impliedWinnerId = !scoresEntered
    ? null
    : Number(home) > Number(away)
      ? match.home_team?.id ?? null
      : Number(away) > Number(home)
        ? match.away_team?.id ?? null
        : drawWinnerId
  const needsDrawWinner = isKnockout && isDraw && !drawWinnerId

  const canSave = scoresEntered && !isPending && !needsDrawWinner

  const save = () => {
    mutate({
      matchId: match.id,
      home_score: Number(home),
      away_score: Number(away),
      winner_team_id: isKnockout ? impliedWinnerId : null,
      decided_by: isKnockout && decidedBy ? decidedBy : null,
    })
  }

  return (
    <div className="rounded-xl bg-gray-800 p-4">
      <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
        <span>{format(new Date(match.kickoff_utc), 'EEE d MMM, HH:mm', { locale: dateLocale })}</span>
        <span>
          {match.group_name ? t('admin.group', { name: match.group_name }) : t(`stages.${match.stage}`)}
          {match.status === 'finished' && (
            <span className="ml-2 text-emerald-400">{t('admin.finished')}</span>
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
          aria-label={t('admin.scoreAria', { team: homeName })}
          className="w-14 rounded-lg border border-gray-600 bg-gray-900 py-1.5 text-center text-white focus:border-emerald-500 focus:outline-none"
        />
        <span className="text-gray-500">–</span>
        <input
          type="number"
          min={0}
          max={99}
          value={away}
          onChange={e => setAway(e.target.value)}
          aria-label={t('admin.scoreAria', { team: awayName })}
          className="w-14 rounded-lg border border-gray-600 bg-gray-900 py-1.5 text-center text-white focus:border-emerald-500 focus:outline-none"
        />
        <span className="flex-1 truncate text-sm font-medium text-white">{awayName}</span>
        <button
          onClick={save}
          disabled={!canSave}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          {t('admin.save')}
        </button>
      </div>

      {/* Knockout: who advanced + how it was decided */}
      {isKnockout && match.home_team && match.away_team && (
        <div className="mt-3 border-t border-gray-700 pt-3">
          <p className="mb-1.5 text-xs text-gray-400">
            {isDraw ? t('admin.pickAdvancing') : t('admin.advancingAuto')}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {[match.home_team, match.away_team].map(team => {
              const selected = impliedWinnerId === team.id
              return (
                <button
                  key={team.id}
                  type="button"
                  onClick={() => isDraw && setDrawWinnerId(team.id)}
                  disabled={!isDraw}
                  className={`truncate rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors ${
                    selected
                      ? 'border-emerald-500 bg-emerald-500/15 text-emerald-300'
                      : 'border-gray-600 bg-gray-900 text-gray-300'
                  } ${isDraw ? 'hover:border-gray-500' : 'cursor-default opacity-80'}`}
                >
                  {localizeTeamName(team.name, i18n.language)}
                </button>
              )
            })}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {DECIDED_BY_OPTIONS.map(opt => (
              <button
                key={opt}
                type="button"
                onClick={() => setDecidedBy(decidedBy === opt ? '' : opt)}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  decidedBy === opt
                    ? 'bg-emerald-600 text-white'
                    : 'bg-gray-900 text-gray-400 hover:text-white'
                }`}
              >
                {t(`admin.decidedBy.${opt}`)}
              </button>
            ))}
          </div>
        </div>
      )}

      {isSuccess && data && (
        <p className="mt-2 text-xs text-emerald-400">
          {t('admin.saved', {
            scored: data.predictions_scored,
            recomputed: data.leaderboards_recomputed,
          })}
        </p>
      )}
      {isError && (
        <p className="mt-2 text-xs text-red-400">
          {t('admin.saveFailed', {
            error: error instanceof Error ? error.message : t('admin.unknownError'),
          })}
        </p>
      )}
    </div>
  )
}
