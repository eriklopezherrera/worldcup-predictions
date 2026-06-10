import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import { forgotPassword, confirmForgotPassword } from '../lib/auth'

type Stage = 'email' | 'reset'

export default function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [stage, setStage] = useState<Stage>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      await forgotPassword(email)
      setStage('reset')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to send reset code.')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleResetSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      await confirmForgotPassword(email, code.trim(), newPassword)
      navigate('/login', { replace: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Password reset failed.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-900 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600">
            <KeyRound className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">
            {stage === 'email' ? 'Forgot password?' : 'Reset password'}
          </h1>
          <p className="mt-1 text-center text-sm text-gray-400">
            {stage === 'email'
              ? "Enter your email and we'll send a reset code"
              : `Enter the code sent to ${email}`}
          </p>
        </div>

        <div className="rounded-xl bg-gray-800 p-6 shadow-lg">
          {error && (
            <div className="mb-4 rounded-lg bg-red-900/50 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {stage === 'email' ? (
            <form onSubmit={handleEmailSubmit}>
              <div className="mb-6">
                <label className="mb-1.5 block text-sm font-medium text-gray-300">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  placeholder="john@example.com"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoading ? 'Sending code…' : 'Send reset code'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleResetSubmit}>
              <div className="mb-4">
                <label className="mb-1.5 block text-sm font-medium text-gray-300">
                  Verification Code
                </label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  required
                  inputMode="numeric"
                  maxLength={6}
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-center text-2xl tracking-[0.5em] text-white placeholder-gray-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  placeholder="000000"
                />
              </div>
              <div className="mb-6">
                <label className="mb-1.5 block text-sm font-medium text-gray-300">
                  New Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  minLength={8}
                  className="w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-white placeholder-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  placeholder="At least 8 characters"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || code.length !== 6}
                className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoading ? 'Resetting…' : 'Reset password'}
              </button>
            </form>
          )}
        </div>

        <p className="mt-4 text-center text-sm text-gray-400">
          <Link to="/login" className="font-medium text-emerald-400 hover:text-emerald-300">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
