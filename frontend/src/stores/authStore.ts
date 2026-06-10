import { create } from 'zustand'
import type { CognitoUser } from 'amazon-cognito-identity-js'
import * as cognitoAuth from '../lib/auth'
import type { AuthTokens } from '../lib/auth'
import {
  MOCK_AUTH,
  DEV_USER_ID,
  hasMockSession,
  startMockSession,
  endMockSession,
} from '../lib/devAuth'

// In mock mode we don't have real JWTs. We store the dev user id in the
// `idToken` slot purely so `tokens` is truthy (route guards key off it); the
// apiClient sends the id via the `X-Dev-User-Id` header instead of Bearer auth.
const mockTokens = (): AuthTokens => ({
  accessToken: 'mock',
  idToken: DEV_USER_ID ?? '',
  refreshToken: 'mock',
})

interface AuthState {
  user: CognitoUser | null
  tokens: AuthTokens | null
  isLoading: boolean
  initialize: () => Promise<void>
  login: (usernameOrEmail: string, password: string) => Promise<void>
  logout: () => void
  refreshTokens: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  tokens: null,
  isLoading: true,

  initialize: async () => {
    set({ isLoading: true })
    if (MOCK_AUTH) {
      set({ user: null, tokens: hasMockSession() ? mockTokens() : null, isLoading: false })
      return
    }
    try {
      const tokens = await cognitoAuth.getStoredSession()
      const user = cognitoAuth.getCurrentUser()
      set({ user, tokens, isLoading: false })
    } catch {
      set({ user: null, tokens: null, isLoading: false })
    }
  },

  login: async (usernameOrEmail, password) => {
    set({ isLoading: true })
    if (MOCK_AUTH) {
      startMockSession()
      set({ user: null, tokens: mockTokens(), isLoading: false })
      return
    }
    try {
      const { user, tokens } = await cognitoAuth.login(usernameOrEmail, password)
      set({ user, tokens, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
      throw err
    }
  },

  logout: () => {
    if (MOCK_AUTH) {
      endMockSession()
      set({ user: null, tokens: null })
      return
    }
    cognitoAuth.logout()
    set({ user: null, tokens: null })
  },

  refreshTokens: async () => {
    if (MOCK_AUTH) {
      set({ tokens: mockTokens() })
      return
    }
    try {
      const tokens = await cognitoAuth.refreshSession()
      set({ tokens })
    } catch {
      cognitoAuth.logout()
      set({ user: null, tokens: null })
    }
  },
}))
