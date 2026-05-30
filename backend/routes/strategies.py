"""
Strategy routes.

GET /api/strategies  – list available strategies
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.backtest import Strategy
from backend.schemas.backtest import StrategyResponse

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyResponse])
def list_strategies(db: Session = Depends(get_db)) -> list[Strategy]:
    """Return all registered strategies ordered alphabetically."""
    return db.query(Strategy).order_by(Strategy.name).all()
