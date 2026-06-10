import { Minus, Plus } from 'lucide-react'

interface ScoreInputProps {
  value: number
  onChange: (val: number) => void
  disabled?: boolean
}

const MIN = 0
const MAX = 30

export default function ScoreInput({ value, onChange, disabled }: ScoreInputProps) {
  const dec = () => onChange(Math.max(MIN, value - 1))
  const inc = () => onChange(Math.min(MAX, value + 1))

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={dec}
        disabled={disabled || value <= MIN}
        className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-white hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Decrease"
      >
        <Minus size={14} />
      </button>
      <input
        type="number"
        min={MIN}
        max={MAX}
        value={value}
        onChange={e =>
          onChange(Math.min(MAX, Math.max(MIN, parseInt(e.target.value, 10) || 0)))
        }
        disabled={disabled}
        className="w-10 text-center bg-gray-700 border border-gray-600 rounded text-white font-bold text-lg py-1 disabled:opacity-50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none focus:outline-none focus:border-emerald-500"
        aria-label="Score"
      />
      <button
        type="button"
        onClick={inc}
        disabled={disabled || value >= MAX}
        className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-white hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        aria-label="Increase"
      >
        <Plus size={14} />
      </button>
    </div>
  )
}
