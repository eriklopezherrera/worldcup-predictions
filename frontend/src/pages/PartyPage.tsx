import { useParams } from 'react-router-dom'

export default function PartyPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Party</h1>
      <p className="mt-2 text-gray-400">Members and leaderboard for party {id}</p>
    </div>
  )
}
