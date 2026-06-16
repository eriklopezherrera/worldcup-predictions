import { RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useRegisterSW } from 'virtual:pwa-register/react'

// How often (ms) an open tab re-checks the server for a new service worker, so
// long-lived sessions still learn about a deploy without a manual reload.
const UPDATE_CHECK_INTERVAL = 60_000

export default function PwaUpdatePrompt() {
  const { t } = useTranslation()
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_swUrl, registration) {
      if (!registration) return
      setInterval(() => {
        // Only poll when online; update() throws/no-ops otherwise.
        if (navigator.onLine) registration.update()
      }, UPDATE_CHECK_INTERVAL)
    },
  })

  if (!needRefresh) return null

  return (
    <div className="fixed inset-x-0 bottom-20 z-50 flex justify-center px-4 md:bottom-6">
      <div className="flex items-center gap-3 rounded-xl border border-gray-700 bg-gray-800 px-4 py-3 shadow-lg">
        <span className="text-sm text-gray-200">{t('pwa.newVersion')}</span>
        <button
          onClick={() => updateServiceWorker(true)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
        >
          <RefreshCw size={14} />
          {t('pwa.refresh')}
        </button>
      </div>
    </div>
  )
}
