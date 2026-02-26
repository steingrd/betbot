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


class TaskStarted(BaseModel):
    task_id: str
    task_type: str


class ChatMessageRequest(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str | None = None
