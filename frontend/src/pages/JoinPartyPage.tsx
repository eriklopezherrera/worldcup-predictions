import { useParams } from 'react-router-dom'

export default function JoinPartyPage() {
  const { code } = useParams<{ code: string }>()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-900 px-4">
      <div className="w-full max-w-sm rounded-xl bg-gray-800 p-6 shadow-lg">
        <h1 className="text-2xl font-bold text-white">Join Party</h1>
        <p className="mt-2 text-gray-400">
          You&apos;ve been invited with code <span className="font-mono text-emerald-400">{code}</span>.
        </p>
      </div>
    </div>
  )
}
