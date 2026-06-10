import {
  CognitoUser,
  CognitoUserPool,
  CognitoUserAttribute,
  AuthenticationDetails,
  CognitoUserSession,
  CognitoRefreshToken,
} from 'amazon-cognito-identity-js'

const userPool = new CognitoUserPool({
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID as string,
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID as string,
})

export interface AuthTokens {
  accessToken: string
  idToken: string
  refreshToken: string
}

function extractTokens(session: CognitoUserSession): AuthTokens {
  return {
    accessToken: session.getAccessToken().getJwtToken(),
    idToken: session.getIdToken().getJwtToken(),
    refreshToken: session.getRefreshToken().getToken(),
  }
}

export function getCurrentUser(): CognitoUser | null {
  return userPool.getCurrentUser()
}

export function getStoredSession(): Promise<AuthTokens | null> {
  return new Promise((resolve) => {
    const user = userPool.getCurrentUser()
    if (!user) return resolve(null)
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session?.isValid()) return resolve(null)
      resolve(extractTokens(session))
    })
  })
}

export function login(
  usernameOrEmail: string,
  password: string,
): Promise<{ user: CognitoUser; tokens: AuthTokens }> {
  return new Promise((resolve, reject) => {
    const authDetails = new AuthenticationDetails({
      Username: usernameOrEmail,
      Password: password,
    })
    const user = new CognitoUser({ Username: usernameOrEmail, Pool: userPool })
    user.authenticateUser(authDetails, {
      onSuccess: (session) => resolve({ user, tokens: extractTokens(session) }),
      onFailure: reject,
    })
  })
}

export function register(username: string, email: string, password: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const attributes = [new CognitoUserAttribute({ Name: 'email', Value: email })]
    userPool.signUp(username, password, attributes, [], (err) => {
      if (err) return reject(err)
      resolve()
    })
  })
}

export function confirmEmail(username: string, code: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: username, Pool: userPool })
    user.confirmRegistration(code, true, (err) => {
      if (err) return reject(err)
      resolve()
    })
  })
}

export function resendConfirmationCode(username: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: username, Pool: userPool })
    user.resendConfirmationCode((err) => {
      if (err) return reject(err)
      resolve()
    })
  })
}

export function logout(): void {
  userPool.getCurrentUser()?.signOut()
}

export function refreshSession(): Promise<AuthTokens> {
  return new Promise((resolve, reject) => {
    const user = userPool.getCurrentUser()
    if (!user) return reject(new Error('No current user'))
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session) return reject(err ?? new Error('No session'))
      const refreshToken = new CognitoRefreshToken({
        RefreshToken: session.getRefreshToken().getToken(),
      })
      user.refreshSession(refreshToken, (refreshErr, newSession: CognitoUserSession) => {
        if (refreshErr) return reject(refreshErr)
        resolve(extractTokens(newSession))
      })
    })
  })
}

export function forgotPassword(email: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    user.forgotPassword({
      onSuccess: () => resolve(),
      onFailure: reject,
    })
  })
}

export function confirmForgotPassword(
  email: string,
  code: string,
  newPassword: string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool })
    user.confirmPassword(code, newPassword, {
      onSuccess: () => resolve(),
      onFailure: reject,
    })
  })
}
