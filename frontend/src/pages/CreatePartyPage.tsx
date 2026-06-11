import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Check, Copy, PartyPopper } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useCreateParty } from '../hooks/useParties'
import { useTournaments } from '../hooks/useTournaments'
import type { Party } from '../types'

export default function CreatePartyPage() {
  const { t } = useTranslation()
  const { data: tournaments = [] } = useTournaments()
  const createParty = useCreateParty()

  const [name, setName] = useState('')
  const [tournamentId, setTournamentId] = useState('')
  const [error, setError] = useState('')
  const [created, setCreated] = useState<Party | null>(null)
  const [copied, setCopied] = useState<'code' | 'link' | null>(null)

  const inviteLink = created
    ? `${window.location.origin}/parties/join/${created.invite_code}`
    : ''

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setError('')
    try {
      const party = await createParty.mutateAsync({
        name: name.trim(),
        tournament_id: tournamentId || undefined,
      })
      setCreated(party)
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          t('createParty.createFailed'),
      )
    }
  }

  async function copy(value: string, which: 'code' | 'link') {
    await navigator.clipboard.writeText(value)
    setCopied(which)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="mx-auto max-w-md pb-24">
      <Link
        to="/parties"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('createParty.backToParties')}
      </Link>

      {created ? (
        <div className="rounded-xl border border-gray-700 bg-gray-800 p-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600">
            <PartyPopper className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">{t('createParty.ready', { name: created.name })}</h1>
          <p className="mt-1 text-sm text-gray-400">
            {t('createParty.shareHint')}
          </p>

          <div className="mt-6 space-y-4 text-left">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-gray-400">
                {t('createParty.inviteCode')}
              </label>
              <div className="flex gap-2">
                <div className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-center font-mono text-lg font-bold tracking-widest text-emerald-400">
                  {created.invite_code}
                </div>
                <button
                  onClick={() => copy(created.invite_code, 'code')}
                  className="flex items-center gap-1.5 rounded-lg bg-gray-700 px-3 text-sm font-medium text-white hover:bg-gray-600"
                >
                  {copied === 'code' ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-gray-400">
                {t('createParty.shareableLink')}
              </label>
              <div className="flex gap-2">
                <div className="min-w-0 flex-1 truncate rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-gray-300">
                  {inviteLink}
                </div>
                <button
                  onClick={() => copy(inviteLink, 'link')}
                  className="flex items-center gap-1.5 rounded-lg bg-gray-700 px-3 text-sm font-medium text-white hover:bg-gray-600"
                >
                  {copied === 'link' ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>

          <Link
            to={`/parties/${created.id}`}
            className="mt-6 block w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500"
          >
            {t('createParty.goToParty')}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="rounded-xl border border-gray-700 bg-gray-800 p-6">
          <h1 className="text-xl font-bold text-white">{t('createParty.title')}</h1>
          <p className="mt-1 text-sm text-gray-400">{t('createParty.subtitle')}</p>

          {error && (
            <div className="mt-4 rounded-lg bg-red-900/50 px-4 py-3 text-sm text-red-300">{error}</div>
          )}

          <div className="mt-5">
            <label className="mb-1.5 block text-sm font-medium text-gray-300">{t('createParty.name')}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              required
              placeholder={t('createParty.namePlaceholder')}
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="mt-4">
            <label className="mb-1.5 block text-sm font-medium text-gray-300">
              {t('createParty.tournament')} <span className="text-gray-500">{t('common.optional')}</span>
            </label>
            <select
              value={tournamentId}
              onChange={(e) => setTournamentId(e.target.value)}
              className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
            >
              <option value="">{t('createParty.allTournaments')}</option>
              {tournaments.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.season ? ` (${t.season})` : ''}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              {t('createParty.tournamentHint')}
            </p>
          </div>

          <button
            type="submit"
            disabled={!name.trim() || createParty.isPending}
            className="mt-6 w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {createParty.isPending ? t('createParty.creating') : t('createParty.create')}
          </button>
        </form>
      )}
    </div>
  )
}
