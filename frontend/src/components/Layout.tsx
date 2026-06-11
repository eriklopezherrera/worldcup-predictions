import { Outlet, NavLink } from 'react-router-dom'
import { Home, Trophy, BarChart3, Users, User, Globe, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useCurrentUser } from '../hooks/useUser'

const baseNavItems = [
  { to: '/tournaments', icon: Home, labelKey: 'nav.home' },
  { to: '/predictions', icon: Trophy, labelKey: 'nav.predictions' },
  { to: '/leaderboard', icon: BarChart3, labelKey: 'nav.leaderboard' },
  { to: '/parties', icon: Users, labelKey: 'nav.parties' },
  { to: '/profile', icon: User, labelKey: 'nav.profile' },
]

const adminNavItem = { to: '/admin', icon: ShieldCheck, labelKey: 'nav.admin' }

export default function Layout() {
  const { t } = useTranslation()
  const { data: currentUser } = useCurrentUser()
  const navItems = currentUser?.is_admin ? [...baseNavItems, adminNavItem] : baseNavItems

  return (
    <div className="flex min-h-screen flex-col bg-gray-900 text-gray-100">
      {/* Desktop top nav */}
      <header className="hidden border-b border-gray-700 bg-gray-800 md:block">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Globe className="h-6 w-6 text-emerald-500" />
            <span className="text-lg font-bold text-white">{t('nav.brand')}</span>
          </div>
          <nav className="flex items-center gap-1">
            {navItems.map(({ to, icon: Icon, labelKey }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-emerald-600 text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {t(labelKey)}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
        <div className="mx-auto max-w-7xl px-4 py-6">
          <Outlet />
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 border-t border-gray-700 bg-gray-800 md:hidden">
        <div className="flex items-center justify-around">
          {navItems.map(({ to, icon: Icon, labelKey }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-1 py-2 text-xs font-medium transition-colors ${
                  isActive ? 'text-emerald-500' : 'text-gray-400'
                }`
              }
            >
              <Icon className="h-5 w-5" />
              {t(labelKey)}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
