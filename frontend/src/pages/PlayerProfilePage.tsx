import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Star, Target, Trophy } from 'lucide-react'
import { format } from 'date-fns'
import { useTranslation } from 'react-i18next'
import { usePublicUser, usePublicUserPredictions } from '../hooks/useUser'
import { useTournaments } from '../hooks/useTournaments'
import { useDateLocale } from '../i18n/useDateLocale'
import { localizeTeamName } from '../i18n/teams'
import type { PublicPrediction } from '../types'

function initials(name: string): string {
  const source = name.trim()
  if (!source) return '?'
  const parts = source.split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function PointsBadge({ points }: { points: number }) {
  const { t } = useTranslation()
  const cls =
    points === 5
      ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
      : points >= 2
        ? 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30'
        : 'text-gray-400 bg-gray-700 border-gray-600'
  return (
    <span className={`inline-block whitespace-nowrap rounded border px-2 py-0.5 text-xs font-bold ${cls}`}>
      {t('match.pointsBadge', { points: points > 0 ? `+${points}` : '0' })}
    </span>
  )
}

function StatCard({
  icon,
  value,
  label,
  accent,
}: {
  icon: React.ReactNode
  value: string | number
  label: string
  accent: string
}) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800 p-3 text-center">
      <div className="mb-1 flex justify-center">{icon}</div>
      <div className={`text-lg font-bold tabular-nums ${accent}`}>{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  )
}

function PredictionRow({ pred }: { pred: PublicPrediction }) {
  const { t, i18n } = useTranslation()
  const dateLocale = useDateLocale()
  const home = localizeTeamName(pred.home_team?.name, i18n.language) || t('common.tbd')
  const away = localizeTeamName(pred.away_team?.name, i18n.language) || t('common.tbd')

  return (
    <div className="rounded-xl bg-gray-800 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          {format(new Date(pred.kickoff_utc), 'EEE d MMM', { locale: dateLocale })}
        </span>
        <PointsBadge points={pred.total_points} />
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-right text-sm text-gray-200">{home}</span>
        <div className="shrink-0 text-center">
          <div className="text-lg font-bold tabular-nums text-white">
            {pred.home_score} – {pred.away_score}
          </div>
          <div className="mt-0.5 text-xs text-gray-500">
            {t('player.pick', {
              home: pred.predicted_home_score,
              away: pred.predicted_away_score,
            })}
          </div>
        </div>
        <span className="min-w-0 flex-1 truncate text-left text-sm text-gray-200">{away}</span>
      </div>
    </div>
  )
}

export default function PlayerProfilePage() {
  const { t } = useTranslation()
  const { userId } = useParams<{ userId: string }>()
  const { data: tournaments = [] } = useTournaments()
  const activeTournament = tournaments.find((t) => t.status === 'active') ?? tournaments[0]

  const [tournamentId, setTournamentId] = useState<string | undefined>(undefined)
  useEffect(() => {
    if (!tournamentId && activeTournament?.id) setTournamentId(activeTournament.id)
  }, [activeTournament?.id, tournamentId])

  const { data: user } = usePublicUser(userId)
  const { data: predictions = [], isLoading } = usePublicUserPredictions(userId, tournamentId)

  const stats = useMemo(() => {
    return {
      total_points: predictions.reduce((sum, p) => sum + p.total_points, 0),
      exact_scores: predictions.filter((p) => p.points_exact > 0).length,
      predictions_made: predictions.length,
    }
  }, [predictions])

  const name = user?.display_name ?? user?.username ?? ''

  return (
    <div className="mx-auto max-w-2xl pb-24">
      <Link
        to="/leaderboard"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('player.back')}
      </Link>

      {/* Identity */}
      <div className="mb-6 flex items-center gap-4 rounded-xl border border-gray-700 bg-gray-800 p-5">
        {user?.avatar_url ? (
          <img src={user.avatar_url} alt="" className="h-14 w-14 rounded-full object-cover" />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gray-700 text-lg font-bold text-gray-200">
            {initials(name)}
          </div>
        )}
        <div className="min-w-0">
          <div className="truncate text-xl font-bold text-white">{name || '—'}</div>
          {user?.display_name && (
            <div className="truncate text-sm text-gray-400">@{user.username}</div>
          )}
        </div>
      </div>

      {/* Tournament selector */}
      {tournaments.length > 1 && (
        <div className="mb-4">
          <select
            value={tournamentId ?? ''}
            onChange={(e) => setTournamentId(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
          >
            {tournaments.map((tn) => (
              <option key={tn.id} value={tn.id}>
                {tn.name}
                {tn.season ? ` (${tn.season})` : ''}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <StatCard
          icon={<Trophy className="h-4 w-4 text-emerald-400" />}
          value={stats.total_points}
          label={t('player.totalPoints')}
          accent="text-white"
        />
        <StatCard
          icon={<Star className="h-4 w-4 text-yellow-400" />}
          value={stats.exact_scores}
          label={t('player.exactScores')}
          accent="text-yellow-400"
        />
        <StatCard
          icon={<Target className="h-4 w-4 text-blue-400" />}
          value={stats.predictions_made}
          label={t('player.predictions')}
          accent="text-emerald-400"
        />
      </div>

      <h2 className="mb-3 text-lg font-semibold text-white">{t('player.scoredPredictions')}</h2>

      {isLoading ? (
        <div className="py-12 text-center text-gray-400">{t('player.loading')}</div>
      ) : predictions.length === 0 ? (
        <div className="py-12 text-center text-gray-500">{t('player.empty')}</div>
      ) : (
        <div className="flex flex-col gap-3">
          {predictions.map((p) => (
            <PredictionRow key={p.match_id} pred={p} />
          ))}
        </div>
      )}
    </div>
  )
}
