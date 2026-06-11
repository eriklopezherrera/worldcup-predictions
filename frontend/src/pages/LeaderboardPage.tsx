import { useEffect, useMemo, useState } from 'react'
import { Crown } from 'lucide-react'
import { useTournaments } from '../hooks/useTournaments'
import { useParties } from '../hooks/useParties'
import { useGlobalLeaderboard, usePartyLeaderboard } from '../hooks/useLeaderboard'
import { useCurrentUser } from '../hooks/useUser'
import LeaderboardTable from '../components/LeaderboardTable'
import type { LeaderboardEntry } from '../types'

// `global` selects the tournament-wide board; any other value is a party id.
type Tab = 'global' | string

function podiumInitials(entry: LeaderboardEntry): string {
  const source = (entry.display_name ?? entry.username ?? '').trim()
  if (!source) return '?'
  const parts = source.split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function PodiumCard({
  entry,
  place,
}: {
  entry: LeaderboardEntry
  place: 1 | 2 | 3
}) {
  const styles = {
    1: { ring: 'ring-yellow-400', size: 'h-16 w-16 text-xl', pad: 'pb-8', order: 'order-2' },
    2: { ring: 'ring-gray-300', size: 'h-12 w-12 text-base', pad: 'pb-4', order: 'order-1' },
    3: { ring: 'ring-amber-700', size: 'h-12 w-12 text-base', pad: 'pb-4', order: 'order-3' },
  }[place]
  const medal = place === 1 ? '🥇' : place === 2 ? '🥈' : '🥉'

  return (
    <div className={`flex flex-1 flex-col items-center ${styles.order}`}>
      {place === 1 && <Crown className="mb-1 h-5 w-5 text-yellow-400" />}
      <div className={`relative flex items-center justify-center rounded-full bg-gray-700 font-bold text-white ring-2 ${styles.ring} ${styles.size}`}>
        {entry.avatar_url ? (
          <img src={entry.avatar_url} alt="" className="h-full w-full rounded-full object-cover" />
        ) : (
          podiumInitials(entry)
        )}
        <span className="absolute -bottom-1 -right-1 text-lg">{medal}</span>
      </div>
      <div
        className={`mt-3 flex w-full flex-col items-center rounded-t-xl bg-gray-800 px-2 pt-3 ${styles.pad}`}
      >
        <span className="max-w-full truncate text-sm font-semibold text-white">
          {entry.display_name ?? entry.username}
        </span>
        <span className="mt-0.5 text-lg font-bold text-emerald-400 tabular-nums">
          {entry.total_points}
        </span>
        <span className="text-xs text-gray-500">pts</span>
      </div>
    </div>
  )
}

function Podium({ entries }: { entries: LeaderboardEntry[] }) {
  if (entries.length === 0) return null
  const [first, second, third] = entries
  return (
    <div className="mb-6 flex items-end justify-center gap-2">
      {second ? <PodiumCard entry={second} place={2} /> : <div className="flex-1 order-1" />}
      <PodiumCard entry={first} place={1} />
      {third ? <PodiumCard entry={third} place={3} /> : <div className="flex-1 order-3" />}
    </div>
  )
}

export default function LeaderboardPage() {
  const { data: tournaments = [] } = useTournaments()
  const { data: parties = [] } = useParties()
  const { data: currentUser } = useCurrentUser()

  const activeTournament = tournaments.find((t) => t.status === 'active') ?? tournaments[0]
  const [tournamentId, setTournamentId] = useState<string | undefined>(undefined)
  const [tab, setTab] = useState<Tab>('global')

  useEffect(() => {
    if (!tournamentId && activeTournament?.id) {
      setTournamentId(activeTournament.id)
    }
  }, [activeTournament?.id, tournamentId])

  const isGlobal = tab === 'global'

  // The "Global" tab resolves to the tournament's global party (every user is
  // auto-joined to it), so it reuses the same party-leaderboard endpoint.
  const globalQuery = useGlobalLeaderboard(isGlobal ? tournamentId : undefined)
  const partyQuery = usePartyLeaderboard(isGlobal ? undefined : tab, tournamentId)

  const { data, isLoading } = isGlobal ? globalQuery : partyQuery
  const entries = useMemo(() => data?.entries ?? [], [data])

  // Hide the podium until at least one match is scored — otherwise it shows an
  // arbitrary trio of players tied at 0 points.
  const hasScores = useMemo(() => entries.some((e) => e.total_points > 0), [entries])

  return (
    <div className="mx-auto max-w-2xl pb-24">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-white">Leaderboard</h1>
        {tournaments.length > 1 && (
          <select
            value={tournamentId ?? ''}
            onChange={(e) => setTournamentId(e.target.value)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-emerald-500 focus:outline-none"
          >
            {tournaments.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {t.season ? ` (${t.season})` : ''}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Tabs: Global + each party */}
      <div className="mb-6 flex gap-2 overflow-x-auto pb-2 scrollbar-none">
        <button
          onClick={() => setTab('global')}
          className={`flex-shrink-0 whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
            isGlobal ? 'bg-emerald-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          🌍 Global
        </button>
        {parties
          .filter((p) => !p.is_global)
          .map((p) => (
            <button
              key={p.id}
              onClick={() => setTab(p.id)}
              className={`flex-shrink-0 whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                tab === p.id ? 'bg-emerald-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {p.name}
            </button>
          ))}
      </div>

      {hasScores && <Podium entries={entries.slice(0, 3)} />}

      <LeaderboardTable entries={entries} currentUserId={currentUser?.id} isLoading={isLoading} />
    </div>
  )
}
