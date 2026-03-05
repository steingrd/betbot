"""Betting tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import (
    AccumulatorLeg,
    BetInput,
    BetRecord,
    BetSummary,
    PlacedBetRef,
)
from src.data.bet_repository import BetRepository

router = APIRouter(prefix="/api/bets", tags=["bets"])

_repo: BetRepository | None = None


def _get_repo() -> BetRepository:
    global _repo
    if _repo is None:
        _repo = BetRepository()
    return _repo


@router.post("")
def place_bet(bet: BetInput) -> dict:
    repo = _get_repo()
    if bet.bet_type == "accumulator" and bet.legs:
        bet_id = repo.place_accumulator(
            bet.model_dump(exclude={"legs"}),
            [leg.model_dump() for leg in bet.legs],
        )
    else:
        bet_id = repo.place_bet(bet.model_dump(exclude={"legs"}))
    return {"id": bet_id}


@router.get("")
def list_bets(status: str | None = None, limit: int = 50) -> list[BetRecord]:
    repo = _get_repo()
    rows = repo.get_bets(status=status, limit=limit)
    result = []
    for row in rows:
        legs = None
        if row.get("legs"):
            legs = [AccumulatorLeg(**l) for l in row["legs"]]
        row["legs"] = legs
        result.append(BetRecord(**row))
    return result


@router.get("/summary")
def get_summary() -> BetSummary:
    repo = _get_repo()
    return BetSummary(**repo.get_summary())


@router.get("/placed-ids")
def get_placed_ids() -> list[PlacedBetRef]:
    repo = _get_repo()
    return [PlacedBetRef(**r) for r in repo.get_placed_ids()]


@router.delete("/{bet_id}")
def cancel_bet(bet_id: int) -> dict:
    repo = _get_repo()
    ok = repo.cancel_bet(bet_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bet not found or already settled")
    return {"status": "cancelled"}
