import { useAuthStore } from '../stores/authStore'

export default function ProfilePage() {
  const { user, logout } = useAuthStore()

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Profile</h1>
      <p className="mt-2 text-gray-400">
        Signed in as <span className="text-white">{user?.getUsername() ?? '—'}</span>
      </p>
      <button
        onClick={logout}
        className="mt-6 rounded-lg border border-red-700 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-900/30"
      >
        Sign out
      </button>
    </div>
  )
}
