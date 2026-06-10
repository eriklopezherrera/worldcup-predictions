import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { MailCheck } from 'lucide-react'
import { confirmEmail, resendConfirmationCode } from '../lib/auth'

export default function VerifyEmailPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const username = (location.state as { username?: string } | null)?.username ?? ''

  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username) {
      setError('Username not found. Please go back and register again.')
      return
    }
    setError('')
    setIsLoading(true)
    try {
      await confirmEmail(username, code.trim())
      navigate('/login', { replace: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verification failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleResend() {
    if (!username) return
    setError('')
    setSuccess('')
    try {
      await resendConfirmationCode(username)
      setSuccess('A new code has been sent to your email.')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resend code.')
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-900 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600">
            <MailCheck className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Verify your email</h1>
          <p className="mt-1 text-center text-sm text-gray-400">
            We sent a 6-digit code to your email address
          </p>
        </div>

        <form onSubmit={handleSubmit} className="rounded-xl bg-gray-800 p-6 shadow-lg">
          {error && (
            <div className="mb-4 rounded-lg bg-red-900/50 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-4 rounded-lg bg-emerald-900/50 px-4 py-3 text-sm text-emerald-300">
              {success}
            </div>
          )}

          <div className="mb-6">
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

          <button
            type="submit"
            disabled={isLoading || code.length !== 6}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? 'Verifying…' : 'Verify email'}
          </button>
        </form>

        <div className="mt-4 text-center text-sm text-gray-400">
          Didn&apos;t receive a code?{' '}
          <button
            onClick={handleResend}
            className="font-medium text-emerald-400 hover:text-emerald-300"
          >
            Resend
          </button>
        </div>

        <p className="mt-2 text-center text-sm text-gray-400">
          <Link to="/login" className="font-medium text-emerald-400 hover:text-emerald-300">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
