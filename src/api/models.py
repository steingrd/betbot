"""Pydantic models for API request/response types."""

from __future__ import annotations

from pydantic import BaseModel


class DataStatus(BaseModel):
    total_matches: int
    league_count: int
    latest_date: str | None
    model_version: str | None
    acc_1x2: float | None
    acc_over25: float | None
    acc_btts: float | None


class MatchResult(BaseModel):
    date: str
    country: str | None
    league: str | None
    home_team: str
    home_goals: int
    away_goals: int
    away_team: str


class StrategySignalResponse(BaseModel):
    strategy: str
    prob: float
    edge: float
    is_value: bool


class Prediction(BaseModel):
    home_team: str
    away_team: str
    league: str
    kickoff: str
    market: str
    model_prob: float | None
    edge: float | None
    confidence: str
    odds_home: float | None
    odds_draw: float | None
    odds_away: float | None
    consensus_count: int | None = None
    total_strategies: int | None = None
    signals: list[StrategySignalResponse] | None = None


class SafePick(BaseModel):
    home_team: str
    away_team: str
    league: str | None
    kickoff: str
    predicted_outcome: str
    avg_prob: float
    consensus_count: int
    total_strategies: int
    odds: float | None
    strategy_probs: dict[str, float]


class Accumulator(BaseModel):
    size: int
    combined_odds: float
    min_prob: float
    avg_prob: float
    picks: list[SafePick]


class ConfidentGoalPick(BaseModel):
    home_team: str
    away_team: str
    league: str | None
    kickoff: str
    market: str
    avg_prob: float
    consensus_count: int
    total_strategies: int
    strategy_probs: dict[str, float]


class AllPredictions(BaseModel):
    value_bets: list[Prediction]
    safe_picks: list[SafePick]
    accumulators: list[Accumulator]
    confident_goals: list[ConfidentGoalPick]


class TaskStarted(BaseModel):
    task_id: str
    task_type: str


class BetInput(BaseModel):
    match_id: str | None = None
    bet_type: str = "single"
    market: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    kickoff: str | None = None
    league: str | None = None
    odds: float
    amount: float
    model_prob: float | None = None
    edge: float | None = None
    consensus_count: int | None = None
    legs: list["AccumulatorLegInput"] | None = None


class AccumulatorLegInput(BaseModel):
    match_id: str | None = None
    market: str
    home_team: str
    away_team: str
    kickoff: str | None = None
    odds: float | None = None


class AccumulatorLeg(BaseModel):
    id: int
    bet_id: int
    match_id: str | None
    market: str
    home_team: str
    away_team: str
    kickoff: str | None
    odds: float | None
    result: str


class BetRecord(BaseModel):
    id: int
    match_id: str | None
    bet_type: str
    market: str | None
    home_team: str | None
    away_team: str | None
    kickoff: str | None
    league: str | None
    odds: float
    amount: float
    model_prob: float | None
    edge: float | None
    consensus_count: int | None
    status: str
    payout: float | None
    profit: float | None
    created_at: str
    settled_at: str | None
    legs: list[AccumulatorLeg] | None = None


class BetSummary(BaseModel):
    active_count: int
    active_amount: float
    max_potential_payout: float = 0.0
    latest_kickoff: str | None = None
    total_staked: float
    total_payout: float
    net_profit: float
    roi_pct: float
    win_count: int
    loss_count: int


class PlacedBetRef(BaseModel):
    match_id: str | None
    market: str | None
    bet_type: str


class ChatMessageRequest(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str | None = None
