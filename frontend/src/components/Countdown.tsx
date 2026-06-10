import { useEffect, useState } from 'react'

interface CountdownProps {
  kickoffUtc: string
}

interface TimeLeft {
  h: number
  m: number
  s: number
  totalSecs: number
}

function computeTimeLeft(kickoffUtc: string): TimeLeft | null {
  const diff = new Date(kickoffUtc).getTime() - Date.now()
  if (diff <= 0) return null
  const totalSecs = Math.floor(diff / 1000)
  return {
    h: Math.floor(totalSecs / 3600),
    m: Math.floor((totalSecs % 3600) / 60),
    s: totalSecs % 60,
    totalSecs,
  }
}

export default function Countdown({ kickoffUtc }: CountdownProps) {
  const [timeLeft, setTimeLeft] = useState<TimeLeft | null>(() => computeTimeLeft(kickoffUtc))

  useEffect(() => {
    const id = setInterval(() => setTimeLeft(computeTimeLeft(kickoffUtc)), 1000)
    return () => clearInterval(id)
  }, [kickoffUtc])

  if (!timeLeft) return null

  const isUrgent = timeLeft.totalSecs < 30 * 60
  const pad = (n: number) => String(n).padStart(2, '0')
  const label =
    timeLeft.h > 0
      ? `Locks in ${timeLeft.h}h ${pad(timeLeft.m)}m ${pad(timeLeft.s)}s`
      : `Locks in ${timeLeft.m}m ${pad(timeLeft.s)}s`

  return (
    <span
      className={`text-xs font-medium tabular-nums transition-colors ${
        isUrgent ? 'text-red-400' : 'text-gray-400'
      }`}
    >
      {label}
    </span>
  )
}
