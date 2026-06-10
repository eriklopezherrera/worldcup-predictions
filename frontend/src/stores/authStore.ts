import { create } from 'zustand'
import type { CognitoUser } from 'amazon-cognito-identity-js'
import * as cognitoAuth from '../lib/auth'
import type { AuthTokens } from '../lib/auth'

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
    try {
      const { user, tokens } = await cognitoAuth.login(usernameOrEmail, password)
      set({ user, tokens, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
      throw err
    }
  },

  logout: () => {
    cognitoAuth.logout()
    set({ user: null, tokens: null })
  },

  refreshTokens: async () => {
    try {
      const tokens = await cognitoAuth.refreshSession()
      set({ tokens })
    } catch {
      cognitoAuth.logout()
      set({ user: null, tokens: null })
    }
  },
}))
