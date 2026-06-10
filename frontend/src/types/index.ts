export type TournamentStatus = 'upcoming' | 'active' | 'finished'
export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled'
export type MatchStage =
  | 'group_stage'
  | 'round_of_16'
  | 'quarter_final'
  | 'semi_final'
  | 'third_place'
  | 'final'
export type PartyRole = 'member' | 'admin'

export interface Tournament {
  id: string
  name: string
  season: string
  country?: string | null
  logo_url?: string | null
  status: TournamentStatus
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
  home_team: Team
  away_team: Team
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

export interface LeaderboardEntry {
  user_id: string
  username: string
  display_name?: string | null
  avatar_url?: string | null
  total_points: number
  exact_scores: number
  predictions_made: number
  rank: number
}

export interface LeaderboardResponse {
  party_id: string
  tournament_id: string
  entries: LeaderboardEntry[]
  computed_at?: string | null
}

export interface ApiError {
  detail: string
  code?: string
}
