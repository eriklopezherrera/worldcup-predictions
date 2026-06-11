import { useTranslation } from 'react-i18next'
import { enUS, es } from 'date-fns/locale'
import type { Locale } from 'date-fns'

/**
 * Returns the date-fns locale matching the current UI language, so `format()`
 * calls render month/day names in the right language. Pass it as the `locale`
 * option: `format(date, 'EEE d MMM, HH:mm', { locale })`.
 */
export function useDateLocale(): Locale {
  const { i18n } = useTranslation()
  return i18n.language.startsWith('es') ? es : enUS
}
