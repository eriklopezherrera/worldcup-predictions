import { useState } from 'react'
import { Trophy, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const STORAGE_KEY = 'knockoutScoringNoticeDismissed'

/**
 * Explains the knockout-stage scoring (1 result / 2 exact / 2 advancing) shown
 * on the home and predictions pages. Dismissible; the choice is remembered in
 * localStorage so it doesn't nag after the user has read it.
 */
export default function KnockoutScoringNotice() {
  const { t } = useTranslation()
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(STORAGE_KEY) === '1',
  )

  if (dismissed) return null

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, '1')
    setDismissed(true)
  }

  return (
    <div className="relative mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
      <button
        onClick={dismiss}
        aria-label={t('knockout.dismiss')}
        className="absolute right-2 top-2 rounded-full p-1 text-emerald-300/70 hover:bg-emerald-500/20 hover:text-emerald-200"
      >
        <X size={16} />
      </button>
      <div className="flex items-center gap-2">
        <Trophy size={16} className="text-emerald-400" />
        <h3 className="text-sm font-semibold text-emerald-200">{t('knockout.title')}</h3>
      </div>
      <p className="mt-2 text-xs text-gray-300">{t('knockout.intro')}</p>
      <ul className="mt-1.5 space-y-0.5 text-xs text-gray-300">
        <li>• {t('knockout.p1')}</li>
        <li>• {t('knockout.p2')}</li>
        <li>• {t('knockout.p3')}</li>
      </ul>
      <p className="mt-2 text-xs text-gray-400">{t('knockout.note')}</p>
    </div>
  )
}
