import { useEffect, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import PwaUpdatePrompt from './components/PwaUpdatePrompt'

import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'

import TournamentsPage from './pages/TournamentsPage'
import TournamentPage from './pages/TournamentPage'
import MyPredictionsPage from './pages/MyPredictionsPage'
import LeaderboardPage from './pages/LeaderboardPage'
import PartiesPage from './pages/PartiesPage'
import CreatePartyPage from './pages/CreatePartyPage'
import JoinPartyPage from './pages/JoinPartyPage'
import PartyPage from './pages/PartyPage'
import ProfilePage from './pages/ProfilePage'
import PlayerProfilePage from './pages/PlayerProfilePage'
import AdminPage from './pages/AdminPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
})

function Spinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-900">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
    </div>
  )
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { tokens, isLoading } = useAuthStore()
  if (isLoading) return <Spinner />
  if (!tokens) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const initialize = useAuthStore((s) => s.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <QueryClientProvider client={queryClient}>
      <PwaUpdatePrompt />
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify" element={<VerifyEmailPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/parties/join/:code" element={<JoinPartyPage />} />

          {/* Protected routes — share the Layout shell */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/tournaments" replace />} />
            <Route path="tournaments" element={<TournamentsPage />} />
            <Route path="tournaments/:id" element={<TournamentPage />} />
            <Route path="predictions" element={<MyPredictionsPage />} />
            <Route path="leaderboard" element={<LeaderboardPage />} />
            <Route path="parties" element={<PartiesPage />} />
            <Route path="parties/create" element={<CreatePartyPage />} />
            <Route path="parties/:id" element={<PartyPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="players/:userId" element={<PlayerProfilePage />} />
            <Route path="admin" element={<AdminPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
