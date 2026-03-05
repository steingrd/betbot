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

export interface StrategySignal {
  strategy: string
  prob: number
  edge: number
  is_value: boolean
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
  consensus_count: number | null
  total_strategies: number | null
  signals: StrategySignal[] | null
}

export interface SafePick {
  home_team: string
  away_team: string
  league: string | null
  kickoff: string
  predicted_outcome: string
  avg_prob: number
  consensus_count: number
  total_strategies: number
  odds: number | null
  strategy_probs: Record<string, number>
}

export interface Accumulator {
  size: number
  combined_odds: number
  min_prob: number
  avg_prob: number
  picks: SafePick[]
}

export interface ConfidentGoalPick {
  home_team: string
  away_team: string
  league: string | null
  kickoff: string
  market: string
  avg_prob: number
  consensus_count: number
  total_strategies: number
  strategy_probs: Record<string, number>
}

export interface AllPredictions {
  value_bets: Prediction[]
  safe_picks: SafePick[]
  accumulators: Accumulator[]
  confident_goals: ConfidentGoalPick[]
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

export interface AccumulatorLegRecord {
  id: number
  bet_id: number
  match_id: string | null
  market: string
  home_team: string
  away_team: string
  kickoff: string | null
  odds: number | null
  result: string
}

export interface BetRecord {
  id: number
  match_id: string | null
  bet_type: string
  market: string | null
  home_team: string | null
  away_team: string | null
  kickoff: string | null
  league: string | null
  odds: number
  amount: number
  model_prob: number | null
  edge: number | null
  consensus_count: number | null
  model_slug: string | null
  status: string
  payout: number | null
  profit: number | null
  created_at: string
  settled_at: string | null
  legs: AccumulatorLegRecord[] | null
}

export interface BetSummary {
  active_count: number
  active_amount: number
  max_potential_payout: number
  latest_kickoff: string | null
  total_staked: number
  total_payout: number
  net_profit: number
  roi_pct: number
  win_count: number
  loss_count: number
}

export interface PlacedBetRef {
  match_id: string | null
  market: string | null
  bet_type: string
}

export interface ModelInfo {
  slug: string
  name: string
  strategies: string[]
  years: number | null
  is_default: boolean
  created_at: string
  is_trained: boolean
}

export interface BetInput {
  match_id?: string | null
  bet_type: string
  market?: string | null
  home_team?: string | null
  away_team?: string | null
  kickoff?: string | null
  league?: string | null
  odds: number
  amount: number
  model_prob?: number | null
  edge?: number | null
  consensus_count?: number | null
  model_slug?: string | null
  legs?: {
    match_id?: string | null
    market: string
    home_team: string
    away_team: string
    kickoff?: string | null
    odds?: number | null
  }[]
}
