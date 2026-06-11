export type TournamentStatus = 'upcoming' | 'active' | 'finished'
export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'
export type MatchStage =
  | 'group_stage'
  | 'round_of_32'
  | 'round_of_16'
  | 'quarter_final'
  | 'semi_final'
  | 'third_place'
  | 'final'
export type PartyRole = 'member' | 'admin'
/** Stage tabs that can be set as the predictions-page default. */
export type DefaultPredictionStage = 'all' | 'group' | 'knockout'

export interface Tournament {
  id: string
  name: string
  season: string
  country?: string | null
  logo_url?: string | null
  status: TournamentStatus
  default_prediction_stage: DefaultPredictionStage
}

export interface Team {
  id: string
  name: string
  short_name?: string | null
  logo_url?: string | null
}

export interface Match {
  id: string
  tournament_id: string
  /** Null for knockout placeholders whose teams aren't decided yet. */
  home_team: Team | null
  away_team: Team | null
  kickoff_utc: string
  venue?: string | null
  stage: MatchStage
  group_name?: string | null
  match_day?: number | null
  home_score?: number | null
  away_score?: number | null
  home_score_ht?: number | null
  away_score_ht?: number | null
  status: MatchStatus
  is_locked?: boolean
  actual_result?: string | null
  /** Mapped from the API's `my_prediction` field in useMatches. */
  prediction?: Prediction | null
}

export interface Prediction {
  id: string
  match_id: string
  predicted_home_score: number
  predicted_away_score: number
  points_result: number
  points_exact: number
  total_points: number
  is_locked: boolean
}

export interface PredictionSummary {
  total_points: number
  exact_scores: number
  predictions_made: number
}

export interface User {
  id: string
  cognito_sub: string
  username: string
  email: string
  display_name?: string | null
  avatar_url?: string | null
  is_active: boolean
  is_admin: boolean
}

export interface Party {
  id: string
  name: string
  invite_code: string
  created_by: string
  tournament_id?: string | null
  is_global: boolean
  max_members: number
  member_count: number
}

export interface PartyMember {
  user_id: string
  username: string
  display_name?: string | null
  avatar_url?: string | null
  role: PartyRole
}

/** Public party info shown on the invite landing page (before joining). */
export interface PartyPreview extends Party {
  /** Up to 3 leading members, when the API includes them. */
  top_members?: PartyMember[]
}

export interface LeaderboardEntry {
  user_id: string
  username: string
  display_name?: string | null
  avatar_url?: string | null
  total_points: number
  exact_scores: number
  predictions_made: number
  rank: number
  /** Change in rank since the previous snapshot: positive = moved up, negative = moved down, 0/null = no change */
  rank_delta?: number | null
}

export interface LeaderboardResponse {
  /** null for the global board when no global party exists for the tournament. */
  party_id: string | null
  tournament_id: string
  entries: LeaderboardEntry[]
  computed_at?: string | null
}

export interface ApiError {
  detail: string
  code?: string
}
