import { useEffect, useState } from 'react'
import { ChevronUp, ChevronDown, Minus } from 'lucide-react'
import type { LeaderboardEntry } from '../types'

interface LeaderboardTableProps {
  entries: LeaderboardEntry[]
  currentUserId?: string
  /** Rows revealed per "load more" click. Defaults to 50. */
  pageSize?: number
  isLoading?: boolean
}

function initials(entry: LeaderboardEntry): string {
  const source = (entry.display_name ?? entry.username ?? '').trim()
  if (!source) return '?'
  const parts = source.split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function Avatar({ entry }: { entry: LeaderboardEntry }) {
  if (entry.avatar_url) {
    return (
      <img
        src={entry.avatar_url}
        alt=""
        className="h-8 w-8 flex-shrink-0 rounded-full object-cover"
      />
    )
  }
  return (
    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gray-700 text-xs font-semibold text-gray-200">
      {initials(entry)}
    </div>
  )
}

function RankDelta({ delta }: { delta?: number | null }) {
  if (delta == null || delta === 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-gray-500">
        <Minus className="h-3 w-3" />
      </span>
    )
  }
  if (delta > 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-emerald-400">
        <ChevronUp className="h-3 w-3" />
        {delta}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-medium text-red-400">
      <ChevronDown className="h-3 w-3" />
      {Math.abs(delta)}
    </span>
  )
}

export default function LeaderboardTable({
  entries,
  currentUserId,
  pageSize = 50,
  isLoading = false,
}: LeaderboardTableProps) {
  const [visible, setVisible] = useState(pageSize)

  // Reset pagination whenever the underlying dataset changes (e.g. tab/tournament switch).
  useEffect(() => {
    setVisible(pageSize)
  }, [entries, pageSize])

  if (isLoading) {
    return <div className="py-12 text-center text-gray-400">Loading leaderboard…</div>
  }

  if (entries.length === 0) {
    return (
      <div className="py-12 text-center text-gray-500">
        No rankings yet. Make some predictions to get on the board!
      </div>
    )
  }

  const shown = entries.slice(0, visible)
  const hasMore = visible < entries.length

  return (
    <div>
      <div className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-700 text-xs uppercase tracking-wide text-gray-400">
            <tr>
              <th className="px-3 py-3 font-medium">#</th>
              <th className="px-3 py-3 font-medium">Player</th>
              <th className="px-3 py-3 text-right font-medium">Pts</th>
              <th className="hidden px-3 py-3 text-right font-medium sm:table-cell">Exact</th>
              <th className="hidden px-3 py-3 text-right font-medium sm:table-cell">Predictions</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((entry) => {
              const isMe = !!currentUserId && entry.user_id === currentUserId
              return (
                <tr
                  key={entry.user_id}
                  className={`border-b border-gray-700/60 last:border-0 ${
                    isMe ? 'bg-emerald-500/10' : 'hover:bg-gray-700/30'
                  }`}
                >
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`tabular-nums font-semibold ${
                          isMe ? 'text-emerald-400' : 'text-gray-300'
                        }`}
                      >
                        {entry.rank}
                      </span>
                      <RankDelta delta={entry.rank_delta} />
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2.5">
                      <Avatar entry={entry} />
                      <span
                        className={`truncate font-medium ${
                          isMe ? 'text-emerald-300' : 'text-white'
                        }`}
                      >
                        {entry.display_name ?? entry.username}
                        {isMe && <span className="ml-1.5 text-xs text-emerald-500">(you)</span>}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right font-bold tabular-nums text-white">
                    {entry.total_points}
                  </td>
                  <td className="hidden px-3 py-3 text-right tabular-nums text-yellow-400 sm:table-cell">
                    {entry.exact_scores}
                  </td>
                  <td className="hidden px-3 py-3 text-right tabular-nums text-gray-400 sm:table-cell">
                    {entry.predictions_made}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {hasMore && (
        <div className="mt-4 text-center">
          <button
            onClick={() => setVisible((v) => v + pageSize)}
            className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700 hover:text-white"
          >
            Load more ({entries.length - visible} remaining)
          </button>
        </div>
      )}
    </div>
  )
}
