import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Users, Globe, ChevronRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useParties, useJoinParty } from '../hooks/useParties'
import { usePartyLeaderboard } from '../hooks/useLeaderboard'
import { useTournaments } from '../hooks/useTournaments'
import { useCurrentUser } from '../hooks/useUser'
import type { Party } from '../types'

function PartyRow({
  party,
  tournamentId,
  currentUserId,
}: {
  party: Party
  tournamentId?: string
  currentUserId?: string
}) {
  const { t } = useTranslation()
  // Resolve the user's rank within this party for the active tournament.
  const { data: leaderboard } = usePartyLeaderboard(
    party.id,
    party.tournament_id ?? tournamentId,
  )
  const myRank = leaderboard?.entries.find((e) => e.user_id === currentUserId)?.rank

  return (
    <Link
      to={`/parties/${party.id}`}
      className="flex items-center justify-between gap-3 rounded-xl border border-gray-700 bg-gray-800 p-4 transition-colors hover:border-emerald-600/50 hover:bg-gray-700/50"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-gray-700">
          {party.is_global ? (
            <Globe className="h-5 w-5 text-emerald-400" />
          ) : (
            <Users className="h-5 w-5 text-emerald-400" />
          )}
        </div>
        <div className="min-w-0">
          <div className="truncate font-semibold text-white">{party.name}</div>
          <div className="text-xs text-gray-400">
            {t('parties.memberCount', { count: party.member_count })}
          </div>
        </div>
      </div>
      <div className="flex flex-shrink-0 items-center gap-3">
        {myRank != null && (
          <div className="text-right">
            <div className="text-xs text-gray-500">{t('parties.yourRank')}</div>
            <div className="font-bold text-emerald-400 tabular-nums">#{myRank}</div>
          </div>
        )}
        <ChevronRight className="h-4 w-4 text-gray-500" />
      </div>
    </Link>
  )
}

export default function PartiesPage() {
  const { t } = useTranslation()
  const { data: parties = [], isLoading } = useParties()
  const { data: tournaments = [] } = useTournaments()
  const { data: currentUser } = useCurrentUser()
  const joinParty = useJoinParty()
  const navigate = useNavigate()

  const activeTournament = tournaments.find((t) => t.status === 'active') ?? tournaments[0]
  const [code, setCode] = useState('')
  const [error, setError] = useState('')

  // Clear the error once the user edits the code again.
  useEffect(() => {
    if (error) setError('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  async function handleJoin(e: FormEvent) {
    e.preventDefault()
    const trimmed = code.trim()
    if (!trimmed) return
    setError('')
    try {
      const party = await joinParty.mutateAsync(trimmed)
      navigate(`/parties/${party.id}`)
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          t('parties.joinFailed'),
      )
    }
  }

  return (
    <div className="mx-auto max-w-2xl pb-24">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">{t('parties.title')}</h1>
        <Link
          to="/parties/create"
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
        >
          <Plus className="h-4 w-4" />
          {t('parties.create')}
        </Link>
      </div>

      {/* Join with code */}
      <form onSubmit={handleJoin} className="mb-6 rounded-xl border border-gray-700 bg-gray-800 p-4">
        <label className="mb-1.5 block text-sm font-medium text-gray-300">{t('parties.joinWithCode')}</label>
        <div className="flex gap-2">
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder={t('parties.enterCode')}
            className="min-w-0 flex-1 rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-500 focus:border-emerald-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!code.trim() || joinParty.isPending}
            className="flex-shrink-0 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {joinParty.isPending ? t('parties.joining') : t('parties.join')}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
      </form>

      {/* Party list */}
      {isLoading ? (
        <div className="py-12 text-center text-gray-400">{t('parties.loading')}</div>
      ) : parties.length === 0 ? (
        <div className="py-12 text-center text-gray-500">
          {t('parties.empty')}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {parties.map((party) => (
            <PartyRow
              key={party.id}
              party={party}
              tournamentId={activeTournament?.id}
              currentUserId={currentUser?.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
