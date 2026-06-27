import { useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ArrowLeft, CalendarCog, Loader2, Lock, LockOpen, Save } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useTournaments, useTournament } from '../hooks/useTournaments'
import { useMatches } from '../hooks/useMatches'
import { useCurrentUser } from '../hooks/useUser'
import { useUpdateMatch, useSetStageOpen } from '../hooks/useAdmin'
import { localizeTeamName } from '../i18n/teams'
import type { Match, MatchStage, TournamentTeam } from '../types'

const STAGE_ORDER: MatchStage[] = [
  'group_stage',
  'round_of_32',
  'round_of_16',
  'quarter_final',
  'semi_final',
  'third_place',
  'final',
]

// Convert an ISO UTC timestamp to the value a <input type="datetime-local">
// expects, expressed in the browser's local timezone.
function toLocalInput(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`
}

export default function AdminGamesPage() {
  const { t } = useTranslation()
  const { data: currentUser, isLoading: userLoading } = useCurrentUser()
  const { data: tournaments = [] } = useTournaments()

  const [selectedTournamentId, setSelectedTournamentId] = useState<string>()
  const [showAll, setShowAll] = useState(false)

  const tournamentId = selectedTournamentId ?? tournaments[0]?.id
  const { data: tournament } = useTournament(tournamentId)
  const { data: matches = [], isLoading: matchesLoading } = useMatches(tournamentId)

  const teams = useMemo<TournamentTeam[]>(
    () => [...(tournament?.teams ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
    [tournament?.teams],
  )

  const visibleMatches = useMemo(() => {
    const now = new Date()
    const list = showAll
      ? matches
      : matches.filter(m => new Date(m.kickoff_utc) > now)
    return [...list].sort(
      (a, b) => new Date(a.kickoff_utc).getTime() - new Date(b.kickoff_utc).getTime(),
    )
  }, [matches, showAll])

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
        <CalendarCog className="h-6 w-6 text-emerald-500" />
        <h1 className="text-2xl font-bold text-white">{t('admin.games.title')}</h1>
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

      {tournamentId && <StagePanel tournamentId={tournamentId} matches={matches} />}

      <div className="mb-3 mt-6 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          {t('admin.games.fixtures')}
        </h2>
        <button
          onClick={() => setShowAll(v => !v)}
          className="rounded-full bg-gray-800 px-3 py-1 text-xs font-medium text-gray-300 hover:bg-gray-700"
        >
          {showAll ? t('admin.games.showUpcoming') : t('admin.games.showAll')}
        </button>
      </div>

      {matchesLoading ? (
        <div className="text-center py-20 text-gray-400">{t('admin.loadingMatches')}</div>
      ) : visibleMatches.length === 0 ? (
        <div className="text-center py-20 text-gray-400">{t('admin.noneFound')}</div>
      ) : (
        <div className="flex flex-col gap-3">
          {visibleMatches.map(match => (
            <EditMatchRow key={match.id} match={match} teams={teams} />
          ))}
        </div>
      )}
    </div>
  )
}

function StagePanel({
  tournamentId,
  matches,
}: {
  tournamentId: string
  matches: Match[]
}) {
  const { t } = useTranslation()
  const { mutate, isPending, variables } = useSetStageOpen()

  const stages = useMemo(() => {
    const map = new Map<
      MatchStage,
      { total: number; teamsSet: number; openCount: number }
    >()
    for (const m of matches) {
      const s = map.get(m.stage) ?? { total: 0, teamsSet: 0, openCount: 0 }
      s.total += 1
      if (m.home_team && m.away_team) s.teamsSet += 1
      if (m.predictions_open) s.openCount += 1
      map.set(m.stage, s)
    }
    return STAGE_ORDER.filter(s => map.has(s)).map(s => ({ stage: s, ...map.get(s)! }))
  }, [matches])

  return (
    <div className="rounded-xl bg-gray-800 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">
        {t('admin.games.stagePanel')}
      </h2>
      <div className="flex flex-col divide-y divide-gray-700">
        {stages.map(({ stage, total, teamsSet, openCount }) => {
          const allOpen = openCount === total
          const pendingThis = isPending && variables?.stage === stage
          return (
            <div key={stage} className="flex items-center gap-3 py-2.5">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-white">{t(`stages.${stage}`)}</div>
                <div className="text-xs text-gray-400">
                  {t('admin.games.stageMeta', { teamsSet, total })}
                  {openCount > 0 && openCount < total && (
                    <span className="ml-1 text-yellow-500">
                      {t('admin.games.partialOpen', { open: openCount })}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() =>
                  mutate({ tournamentId, stage, predictions_open: !allOpen })
                }
                disabled={pendingThis}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                  allOpen
                    ? 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                    : 'bg-emerald-600 text-white hover:bg-emerald-500'
                }`}
              >
                {pendingThis ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : allOpen ? (
                  <Lock size={13} />
                ) : (
                  <LockOpen size={13} />
                )}
                {allOpen ? t('admin.games.close') : t('admin.games.open')}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function EditMatchRow({ match, teams }: { match: Match; teams: TournamentTeam[] }) {
  const { t, i18n } = useTranslation()
  const { mutate, isPending, isSuccess, isError, error, reset } = useUpdateMatch()

  const [kickoff, setKickoff] = useState(() => toLocalInput(match.kickoff_utc))
  const [homeId, setHomeId] = useState(match.home_team?.id ?? '')
  const [awayId, setAwayId] = useState(match.away_team?.id ?? '')

  const kickoffChanged = kickoff !== toLocalInput(match.kickoff_utc)
  const homeChanged = homeId !== (match.home_team?.id ?? '')
  const awayChanged = awayId !== (match.away_team?.id ?? '')
  const hasChanges = kickoffChanged || homeChanged || awayChanged

  const save = () => {
    reset()
    mutate({
      matchId: match.id,
      ...(kickoffChanged ? { kickoff_utc: new Date(kickoff).toISOString() } : {}),
      ...(homeChanged ? { set_home_team: true, home_team_id: homeId || null } : {}),
      ...(awayChanged ? { set_away_team: true, away_team_id: awayId || null } : {}),
    })
  }

  const teamOptions = (
    <>
      <option value="">{t('common.tbd')}</option>
      {teams.map(team => (
        <option key={team.id} value={team.id}>
          {localizeTeamName(team.name, i18n.language)}
        </option>
      ))}
    </>
  )

  return (
    <div className="rounded-xl bg-gray-800 p-4">
      <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
        <span>{t(`stages.${match.stage}`)}{match.group_name ? ` · ${match.group_name}` : ''}</span>
        {!match.predictions_open && (
          <span className="text-yellow-500">{t('admin.games.closed')}</span>
        )}
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        <select
          value={homeId}
          onChange={e => setHomeId(e.target.value)}
          className="min-w-0 rounded-lg border border-gray-600 bg-gray-900 px-2 py-1.5 text-sm text-white focus:border-emerald-500 focus:outline-none"
        >
          {teamOptions}
        </select>
        <span className="text-gray-500">{t('admin.games.vs')}</span>
        <select
          value={awayId}
          onChange={e => setAwayId(e.target.value)}
          className="min-w-0 rounded-lg border border-gray-600 bg-gray-900 px-2 py-1.5 text-sm text-white focus:border-emerald-500 focus:outline-none"
        >
          {teamOptions}
        </select>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <input
          type="datetime-local"
          value={kickoff}
          onChange={e => setKickoff(e.target.value)}
          aria-label={t('admin.games.kickoffAria')}
          className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-2 py-1.5 text-sm text-white focus:border-emerald-500 focus:outline-none"
        />
        <button
          onClick={save}
          disabled={!hasChanges || isPending}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {t('admin.save')}
        </button>
      </div>

      {isSuccess && (
        <p className="mt-2 text-xs text-emerald-400">{t('admin.games.saved')}</p>
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
