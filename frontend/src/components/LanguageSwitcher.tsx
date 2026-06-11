import { useTranslation } from 'react-i18next'
import { Languages } from 'lucide-react'
import { SUPPORTED_LANGUAGES, type Language } from '../i18n'

/**
 * A small two-option language toggle (Español / English). Persists the choice
 * via i18next's localStorage detector so it survives reloads and logout.
 */
export default function LanguageSwitcher({ className = '' }: { className?: string }) {
  const { t, i18n } = useTranslation()
  const current = i18n.language.startsWith('es') ? 'es' : 'en'

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <Languages className="h-4 w-4 text-gray-400" aria-hidden />
      <div className="inline-flex overflow-hidden rounded-lg border border-gray-600">
        {SUPPORTED_LANGUAGES.map((lng: Language) => (
          <button
            key={lng}
            type="button"
            onClick={() => i18n.changeLanguage(lng)}
            aria-pressed={current === lng}
            className={`px-3 py-1.5 text-sm font-medium transition-colors ${
              current === lng
                ? 'bg-emerald-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            {t(`language.${lng}`)}
          </button>
        ))}
      </div>
    </div>
  )
}
