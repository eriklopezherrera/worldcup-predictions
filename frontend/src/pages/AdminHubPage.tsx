import { Link, Navigate } from 'react-router-dom'
import { CalendarCog, ChevronRight, ClipboardCheck, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useCurrentUser } from '../hooks/useUser'

export default function AdminHubPage() {
  const { t } = useTranslation()
  const { data: currentUser, isLoading } = useCurrentUser()

  if (isLoading) {
    return <div className="text-center py-20 text-gray-400">{t('admin.loading')}</div>
  }
  if (!currentUser?.is_admin) {
    return <Navigate to="/" replace />
  }

  const cards = [
    {
      to: '/admin/scoring',
      icon: ClipboardCheck,
      title: t('admin.hub.scoring.title'),
      desc: t('admin.hub.scoring.desc'),
    },
    {
      to: '/admin/games',
      icon: CalendarCog,
      title: t('admin.hub.games.title'),
      desc: t('admin.hub.games.desc'),
    },
  ]

  return (
    <div className="max-w-2xl mx-auto px-4 pb-24">
      <div className="flex items-center gap-2 py-4">
        <ShieldCheck className="h-6 w-6 text-emerald-500" />
        <h1 className="text-2xl font-bold text-white">{t('admin.title')}</h1>
      </div>

      <div className="flex flex-col gap-3">
        {cards.map(card => (
          <Link
            key={card.to}
            to={card.to}
            className="flex items-center gap-4 rounded-xl bg-gray-800 p-4 transition-colors hover:bg-gray-700/60"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-emerald-600/15 text-emerald-400">
              <card.icon className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-semibold text-white">{card.title}</div>
              <div className="text-sm text-gray-400">{card.desc}</div>
            </div>
            <ChevronRight className="h-5 w-5 shrink-0 text-gray-500" />
          </Link>
        ))}
      </div>
    </div>
  )
}
