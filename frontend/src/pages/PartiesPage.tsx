import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'

export default function PartiesPage() {
  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Parties</h1>
        <Link
          to="/parties/create"
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          <Plus className="h-4 w-4" />
          New party
        </Link>
      </div>
      <p className="mt-2 text-gray-400">Compete with friends in private leaderboards.</p>
    </div>
  )
}
