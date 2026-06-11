import { useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeft, Check, Copy, LogOut, Share2, Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useParty, useLeaveParty } from '../hooks/useParties'
import { usePartyLeaderboard } from '../hooks/useLeaderboard'
import { useTournaments } from '../hooks/useTournaments'
import { useCurrentUser } from '../hooks/useUser'
import LeaderboardTable from '../components/LeaderboardTable'

export default function PartyPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: party, isLoading: partyLoading } = useParty(id)
  const { data: tournaments = [] } = useTournaments()
  const { data: currentUser } = useCurrentUser()
  const leaveParty = useLeaveParty()

  const activeTournament = tournaments.find((t) => t.status === 'active') ?? tournaments[0]
  const tournamentId = party?.tournament_id ?? activeTournament?.id
  const { data: leaderboard, isLoading: lbLoading } = usePartyLeaderboard(id, tournamentId)

  const [copied, setCopied] = useState<'code' | 'link' | null>(null)
  const [error, setError] = useState('')

  const inviteLink = party ? `${window.location.origin}/parties/join/${party.invite_code}` : ''

  async function copy(value: string, which: 'code' | 'link') {
    await navigator.clipboard.writeText(value)
    setCopied(which)
    setTimeout(() => setCopied(null), 2000)
  }

  async function handleLeave() {
    if (!id) return
    if (!window.confirm(t('party.confirmLeave'))) return
    setError('')
    try {
      await leaveParty.mutateAsync(id)
      navigate('/parties')
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          t('party.leaveFailed'),
      )
    }
  }

  if (partyLoading) {
    return <div className="py-12 text-center text-gray-400">{t('party.loading')}</div>
  }
  if (!party) {
    return (
      <div className="py-12 text-center text-gray-500">
        {t('party.notFound')}{' '}
        <Link to="/parties" className="text-emerald-400 hover:text-emerald-300">
          {t('party.backToParties')}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl pb-24">
      <Link
        to="/parties"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('party.backToParties')}
      </Link>

      {/* Header card */}
      <div className="rounded-xl border border-gray-700 bg-gray-800 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold text-white">{party.name}</h1>
            <div className="mt-1 flex items-center gap-1.5 text-sm text-gray-400">
              <Users className="h-4 w-4" />
              {t('parties.memberCount', { count: party.member_count })}
            </div>
          </div>
          {!party.is_global && (
            <button
              onClick={handleLeave}
              disabled={leaveParty.isPending}
              className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-red-700 px-3 py-1.5 text-sm font-medium text-red-400 transition-colors hover:bg-red-900/30 disabled:opacity-50"
            >
              <LogOut className="h-4 w-4" />
              {t('party.leave')}
            </button>
          )}
        </div>

        {!party.is_global && (
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <div className="flex flex-1 items-center justify-between gap-2 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2">
              <span className="text-xs uppercase tracking-wide text-gray-500">{t('party.code')}</span>
              <span className="font-mono text-base font-bold tracking-widest text-emerald-400">
                {party.invite_code}
              </span>
              <button
                onClick={() => copy(party.invite_code, 'code')}
                className="text-gray-400 hover:text-white"
                aria-label={t('party.copyInviteCode')}
              >
                {copied === 'code' ? (
                  <Check className="h-4 w-4 text-emerald-400" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </button>
            </div>
            <button
              onClick={() => copy(inviteLink, 'link')}
              className="flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
            >
              {copied === 'link' ? <Check className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
              {copied === 'link' ? t('party.linkCopied') : t('party.shareInviteLink')}
            </button>
          </div>
        )}

        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      </div>

      {/* Party leaderboard */}
      <h2 className="mb-3 mt-6 text-lg font-semibold text-white">{t('party.leaderboard')}</h2>
      <LeaderboardTable
        entries={leaderboard?.entries ?? []}
        currentUserId={currentUser?.id}
        isLoading={lbLoading}
      />
    </div>
  )
}
