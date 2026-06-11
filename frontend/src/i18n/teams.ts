// Spanish names for the 48 WC2026 nations. Team/country names come from the
// backend in English; this maps them for display when the UI language is `es`.
// Keys are the exact English `name` values served by the API.
const ES_TEAM_NAMES: Record<string, string> = {
  Mexico: 'México',
  'South Africa': 'Sudáfrica',
  'Korea Republic': 'Corea del Sur',
  Czechia: 'Chequia',
  Canada: 'Canadá',
  'Bosnia and Herzegovina': 'Bosnia y Herzegovina',
  Qatar: 'Catar',
  Switzerland: 'Suiza',
  Brazil: 'Brasil',
  Morocco: 'Marruecos',
  Haiti: 'Haití',
  Scotland: 'Escocia',
  'United States': 'Estados Unidos',
  Paraguay: 'Paraguay',
  Australia: 'Australia',
  Türkiye: 'Turquía',
  Germany: 'Alemania',
  'Curaçao': 'Curazao',
  "Côte d'Ivoire": 'Costa de Marfil',
  Ecuador: 'Ecuador',
  Netherlands: 'Países Bajos',
  Japan: 'Japón',
  Sweden: 'Suecia',
  Tunisia: 'Túnez',
  Belgium: 'Bélgica',
  Egypt: 'Egipto',
  Iran: 'Irán',
  'New Zealand': 'Nueva Zelanda',
  Spain: 'España',
  'Cabo Verde': 'Cabo Verde',
  'Saudi Arabia': 'Arabia Saudita',
  Uruguay: 'Uruguay',
  France: 'Francia',
  Senegal: 'Senegal',
  Iraq: 'Irak',
  Norway: 'Noruega',
  Argentina: 'Argentina',
  Algeria: 'Argelia',
  Austria: 'Austria',
  Jordan: 'Jordania',
  Portugal: 'Portugal',
  'DR Congo': 'RD del Congo',
  Uzbekistan: 'Uzbekistán',
  Colombia: 'Colombia',
  England: 'Inglaterra',
  Croatia: 'Croacia',
  Ghana: 'Ghana',
  Panama: 'Panamá',
}

/**
 * Localize a backend-supplied team/country name. Falls back to the original
 * English name for any value not in the map (e.g. knockout placeholders) and
 * for non-Spanish languages.
 */
export function localizeTeamName(name: string | null | undefined, language: string): string {
  if (!name) return name ?? ''
  if (language.startsWith('es')) return ES_TEAM_NAMES[name] ?? name
  return name
}
