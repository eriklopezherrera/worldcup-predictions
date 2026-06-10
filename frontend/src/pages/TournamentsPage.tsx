import { Link } from 'react-router-dom'
import { ChevronRight, Trophy } from 'lucide-react'
import { useTournaments } from '../hooks/useTournaments'
import type { Tournament, TournamentStatus } from '../types'

const STATUS_STYLES: Record<TournamentStatus, string> = {
  active: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  upcoming: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  finished: 'text-gray-400 bg-gray-700 border-gray-600',
}

const STATUS_LABELS: Record<TournamentStatus, string> = {
  active: 'Live',
  upcoming: 'Upcoming',
  finished: 'Finished',
}

export default function TournamentsPage() {
  const { data: tournaments = [], isLoading, isError } = useTournaments()

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      <div className="py-4">
        <h1 className="text-2xl font-bold text-white">Tournaments</h1>
        <p className="mt-1 text-sm text-gray-400">
          Pick a tournament to see matches and submit predictions.
        </p>
      </div>

      {isLoading ? (
        <div className="text-center py-20 text-gray-400">Loading tournaments…</div>
      ) : isError ? (
        <div className="text-center py-20 text-red-400">Failed to load tournaments.</div>
      ) : tournaments.length === 0 ? (
        <div className="text-center py-20 text-gray-500">No tournaments yet.</div>
      ) : (
        <div className="flex flex-col gap-3">
          {tournaments.map(t => (
            <TournamentCard key={t.id} tournament={t} />
          ))}
        </div>
      )}
    </div>
  )
}

function TournamentCard({ tournament }: { tournament: Tournament }) {
  return (
    <Link
      to={`/tournaments/${tournament.id}`}
      className="flex items-center gap-3 bg-gray-800 rounded-xl p-4 hover:bg-gray-700/60 transition-colors"
    >
      {tournament.logo_url ? (
        <img src={tournament.logo_url} alt="" className="w-10 h-10 object-contain flex-shrink-0" />
      ) : (
        <div className="w-10 h-10 rounded-lg bg-gray-700 flex items-center justify-center flex-shrink-0">
          <Trophy size={18} className="text-emerald-400" />
        </div>
      )}

      <div className="flex-1 min-w-0">
        <div className="text-white font-semibold truncate">{tournament.name}</div>
        <div className="text-xs text-gray-400">
          {tournament.season}
          {tournament.country ? ` · ${tournament.country}` : ''}
        </div>
      </div>

      <span
        className={`px-2 py-0.5 rounded-full border text-xs font-medium ${STATUS_STYLES[tournament.status]}`}
      >
        {STATUS_LABELS[tournament.status]}
      </span>
      <ChevronRight size={16} className="text-gray-500 flex-shrink-0" />
    </Link>
  )
}
