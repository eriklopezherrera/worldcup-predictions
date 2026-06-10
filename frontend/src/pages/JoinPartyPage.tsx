import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Globe, Users } from 'lucide-react'
import { usePartyPreview, useJoinParty } from '../hooks/useParties'
import { useAuthStore } from '../stores/authStore'
import type { PartyMember } from '../types'

function MemberAvatar({ member }: { member: PartyMember }) {
  const source = (member.display_name ?? member.username ?? '?').trim()
  const initials = source.slice(0, 2).toUpperCase()
  return (
    <div className="flex flex-col items-center gap-1">
      {member.avatar_url ? (
        <img src={member.avatar_url} alt="" className="h-10 w-10 rounded-full object-cover" />
      ) : (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-700 text-xs font-semibold text-gray-200">
          {initials}
        </div>
      )}
      <span className="max-w-[4.5rem] truncate text-xs text-gray-400">
        {member.display_name ?? member.username}
      </span>
    </div>
  )
}

export default function JoinPartyPage() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const { tokens } = useAuthStore()
  const { data: party, isLoading, isError } = usePartyPreview(code)
  const joinParty = useJoinParty()
  const [error, setError] = useState('')

  async function handleJoin() {
    if (!code) return
    // Not logged in: send to login, then bounce back to this invite page.
    if (!tokens) {
      navigate(`/login?redirect=/parties/join/${code}`)
      return
    }
    setError('')
    try {
      const joined = await joinParty.mutateAsync(code)
      navigate(`/parties/${joined.id}`)
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Could not join this party. The invite may be invalid or full.',
      )
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-900 px-4">
      <div className="w-full max-w-sm rounded-xl bg-gray-800 p-6 shadow-lg">
        <div className="mb-4 flex flex-col items-center text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600">
            {party?.is_global ? (
              <Globe className="h-6 w-6 text-white" />
            ) : (
              <Users className="h-6 w-6 text-white" />
            )}
          </div>
          {isLoading ? (
            <p className="text-gray-400">Loading invite…</p>
          ) : isError || !party ? (
            <>
              <h1 className="text-xl font-bold text-white">Invite not found</h1>
              <p className="mt-1 text-sm text-gray-400">
                The code <span className="font-mono text-emerald-400">{code}</span> doesn&apos;t
                match any party.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-400">You&apos;ve been invited to join</p>
              <h1 className="text-xl font-bold text-white">{party.name}</h1>
              <p className="mt-1 text-sm text-gray-400">
                {party.member_count} {party.member_count === 1 ? 'member' : 'members'}
              </p>
            </>
          )}
        </div>

        {party?.top_members && party.top_members.length > 0 && (
          <div className="mb-4 flex justify-center gap-4 border-t border-gray-700 pt-4">
            {party.top_members.slice(0, 3).map((m) => (
              <MemberAvatar key={m.user_id} member={m} />
            ))}
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg bg-red-900/50 px-4 py-3 text-sm text-red-300">{error}</div>
        )}

        {party && !isError && (
          <button
            onClick={handleJoin}
            disabled={joinParty.isPending}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {joinParty.isPending ? 'Joining…' : tokens ? 'Join Party' : 'Sign in to join'}
          </button>
        )}
      </div>
    </div>
  )
}
