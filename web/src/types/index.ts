export interface DataStatus {
  total_matches: number
  league_count: number
  latest_date: string | null
  model_version: string | null
  acc_1x2: number | null
  acc_over25: number | null
  acc_btts: number | null
}

export interface MatchResult {
  date: string
  country: string | null
  league: string | null
  home_team: string
  home_goals: number
  away_goals: number
  away_team: string
}

export interface Prediction {
  home_team: string
  away_team: string
  league: string
  kickoff: string
  market: string
  model_prob: number | null
  edge: number | null
  confidence: string
  odds_home: number | null
  odds_draw: number | null
  odds_away: number | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}

export interface TaskProgress {
  step: string
  detail: string
  percent?: number
  completed?: number
  total?: number
}

export interface TaskStarted {
  task_id: string
  task_type: string
}
