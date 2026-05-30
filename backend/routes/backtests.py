"""
Backtest routes.

GET  /api/backtests       – list recent backtest runs
POST /api/backtests/run   – execute a backtest and persist the result
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.backtest import BacktestRun
from backend.schemas.backtest import BacktestRequest, BacktestResult, BacktestResultWithCurve
from backend.services.backtest_engine import run_ma_crossover

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("", response_model=list[BacktestResult])
def list_backtests(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[BacktestRun]:
    """Return the most recent backtest runs, newest first."""
    runs = (
        db.query(BacktestRun)
        .order_by(BacktestRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return runs


@router.post("/run", response_model=BacktestResultWithCurve, status_code=status.HTTP_201_CREATED)
def run_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
) -> BacktestResultWithCurve:
    """
    Execute a Moving Average Crossover backtest, persist the summary to the
    database, and return the full result including the equity curve.
    """
    logger.info(
        "Running backtest: ticker=%s short=%d long=%d start=%s end=%s",
        request.ticker,
        request.short_window,
        request.long_window,
        request.start_date,
        request.end_date,
    )

    try:
        metrics = run_ma_crossover(
            ticker=request.ticker,
            short_window=request.short_window,
            long_window=request.long_window,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during backtest execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {exc}",
        ) from exc

    run = BacktestRun(
        strategy_name=request.strategy_name,
        ticker=request.ticker,
        short_window=request.short_window,
        long_window=request.long_window,
        start_date=request.start_date,
        end_date=request.end_date,
        total_return=metrics["total_return"],
        sharpe_ratio=metrics["sharpe_ratio"],
        max_drawdown=metrics["max_drawdown"],
        num_trades=metrics["num_trades"],
        created_at=datetime.now(UTC),
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    logger.info("Backtest saved: id=%d total_return=%.4f", run.id, run.total_return or 0.0)

    return BacktestResultWithCurve(
        id=run.id,
        strategy_name=run.strategy_name,
        ticker=run.ticker,
        short_window=run.short_window,
        long_window=run.long_window,
        start_date=run.start_date,
        end_date=run.end_date,
        total_return=run.total_return,
        sharpe_ratio=run.sharpe_ratio,
        max_drawdown=run.max_drawdown,
        num_trades=run.num_trades,
        created_at=run.created_at,
        equity_curve=metrics["equity_curve"],
    )
