import type { Match } from '../types'

export type TimeFilter = 'upcoming' | 'finished' | 'all'

export const TIME_FILTER_IDS: TimeFilter[] = ['upcoming', 'finished', 'all']

// "Upcoming" = live right now, or not yet kicked off. A match whose kickoff has
// passed is no longer upcoming even if its result hasn't been entered yet (it
// still carries status 'scheduled' until an admin scores it), so we key off the
// kickoff time rather than status alone. Finished/cancelled are never upcoming.
export const isUpcoming = (m: Match) =>
  m.status === 'live' ||
  (m.status !== 'finished' && m.status !== 'cancelled' && new Date(m.kickoff_utc) > new Date())

/** Filter a list of matches by the time dimension (upcoming / finished / all). */
export const filterByTime = (matches: Match[], filter: TimeFilter): Match[] => {
  switch (filter) {
    case 'upcoming':
      return matches.filter(isUpcoming)
    case 'finished':
      return matches.filter(m => !isUpcoming(m))
    default:
      return matches
  }
}
