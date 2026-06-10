import { useEffect, useState } from 'react'
import { Check, LogOut, Pencil, Star, Target, TrendingUp, Trophy, X } from 'lucide-react'
import { useCurrentUser, useUpdateUser } from '../hooks/useUser'
import { usePredictionSummary } from '../hooks/usePredictions'
import { useTournaments } from '../hooks/useTournaments'
import { useGlobalLeaderboard } from '../hooks/useLeaderboard'
import { useAuthStore } from '../stores/authStore'

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
    <div className="rounded-xl border border-gray-700 bg-gray-800 p-4 text-center">
      <div className="mb-1 flex justify-center">{icon}</div>
      <div className={`text-xl font-bold tabular-nums ${accent}`}>{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
    </div>
  )
}

export default function ProfilePage() {
  const { data: user } = useCurrentUser()
  const { data: summary } = usePredictionSummary()
  const { data: tournaments = [] } = useTournaments()
  const updateUser = useUpdateUser()
  const logout = useAuthStore((s) => s.logout)

  const activeTournament = tournaments.find((t) => t.status === 'active') ?? tournaments[0]
  const { data: leaderboard } = useGlobalLeaderboard(activeTournament?.id)
  const bestRank = leaderboard?.entries.find((e) => e.user_id === user?.id)?.rank

  const [editing, setEditing] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  // Seed the edit field from the loaded profile.
  useEffect(() => {
    setName(user?.display_name ?? '')
  }, [user?.display_name])

  async function handleSave() {
    setError('')
    try {
      await updateUser.mutateAsync({ display_name: name.trim() || null })
      setEditing(false)
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Could not update your name.',
      )
    }
  }

  function cancelEdit() {
    setName(user?.display_name ?? '')
    setError('')
    setEditing(false)
  }

  return (
    <div className="mx-auto max-w-2xl pb-24">
      <h1 className="mb-4 text-2xl font-bold text-white">Profile</h1>

      {/* Identity card */}
      <div className="rounded-xl border border-gray-700 bg-gray-800 p-5">
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">
          Display name
        </div>
        {editing ? (
          <div>
            <div className="flex gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                placeholder="Your display name"
                className="min-w-0 flex-1 rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-500 focus:border-emerald-500 focus:outline-none"
              />
              <button
                onClick={handleSave}
                disabled={updateUser.isPending}
                className="flex items-center rounded-lg bg-emerald-600 px-3 text-white hover:bg-emerald-500 disabled:opacity-50"
                aria-label="Save"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={cancelEdit}
                className="flex items-center rounded-lg bg-gray-700 px-3 text-gray-300 hover:bg-gray-600"
                aria-label="Cancel"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="text-lg font-semibold text-white">
              {user?.display_name ?? user?.username ?? '—'}
            </span>
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 text-sm text-emerald-400 hover:text-emerald-300"
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit
            </button>
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 gap-3 border-t border-gray-700 pt-4 sm:grid-cols-2">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Username</div>
            <div className="text-white">{user?.username ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Email</div>
            <div className="truncate text-white">{user?.email ?? '—'}</div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <h2 className="mb-3 mt-6 text-lg font-semibold text-white">Your stats</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<Trophy className="h-4 w-4 text-emerald-400" />}
          value={summary?.total_points ?? 0}
          label="Total Points"
          accent="text-white"
        />
        <StatCard
          icon={<Star className="h-4 w-4 text-yellow-400" />}
          value={summary?.exact_scores ?? 0}
          label="Exact Scores"
          accent="text-yellow-400"
        />
        <StatCard
          icon={<Target className="h-4 w-4 text-blue-400" />}
          value={summary?.predictions_made ?? 0}
          label="Predictions"
          accent="text-emerald-400"
        />
        <StatCard
          icon={<TrendingUp className="h-4 w-4 text-purple-400" />}
          value={bestRank != null ? `#${bestRank}` : '—'}
          label="Best Rank"
          accent="text-purple-400"
        />
      </div>

      {/* Logout */}
      <button
        onClick={logout}
        className="mt-8 flex items-center gap-2 rounded-lg border border-red-700 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-900/30"
      >
        <LogOut className="h-4 w-4" />
        Log out
      </button>
    </div>
  )
}
