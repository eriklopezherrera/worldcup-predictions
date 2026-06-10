// Dev-only mock auth. When VITE_MOCK_AUTH=true the app bypasses Cognito
// entirely and authenticates as a single seeded backend user via the
// `X-Dev-User-Id` header (see backend `get_current_user` MOCK_AUTH path).
// Never enable this in a deployed build.
// `import.meta.env.DEV` is statically false in production builds, so the
// mock path is dead-code-eliminated and can never ship to a deployed env.
export const MOCK_AUTH = import.meta.env.DEV && import.meta.env.VITE_MOCK_AUTH === 'true'

// UUID of the seeded dev user (must match `python -m app.workers.seed`).
export const DEV_USER_ID = import.meta.env.VITE_DEV_USER_ID as string | undefined

const MOCK_SESSION_KEY = 'mockAuthSession'

export function hasMockSession(): boolean {
  return localStorage.getItem(MOCK_SESSION_KEY) === '1'
}

export function startMockSession(): void {
  localStorage.setItem(MOCK_SESSION_KEY, '1')
}

export function endMockSession(): void {
  localStorage.removeItem(MOCK_SESSION_KEY)
}
