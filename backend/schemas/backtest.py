import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TICKER_RE = re.compile(r"^[A-Z0-9.\-\^]{1,20}$")


class BacktestRequest(BaseModel):
    """Request body for POST /api/backtests/run."""

    ticker: str = Field(..., min_length=1, max_length=20, description="Equity ticker symbol (e.g. SPY)")
    short_window: int = Field(default=20, ge=2, le=200, description="Short SMA window in trading days")
    long_window: int = Field(default=50, ge=5, le=500, description="Long SMA window in trading days")
    start_date: str = Field(default="2020-01-01", description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(default="2024-01-01", description="Backtest end date (YYYY-MM-DD)")
    strategy_name: str = Field(default="MA Crossover", description="Strategy label to tag the run")

    @field_validator("ticker")
    @classmethod
    def ticker_upper(cls, v: str) -> str:
        v = v.strip().upper()
        if not _TICKER_RE.match(v):
            raise ValueError(
                f"Invalid ticker '{v}'. Use only letters, digits, '.', '-', or '^' (e.g. SPY, BRK-B, ^GSPC)."
            )
        return v

    @field_validator("long_window")
    @classmethod
    def long_must_exceed_short(cls, v: int, info: Any) -> int:
        short = info.data.get("short_window")
        if short is not None and v <= short:
            raise ValueError(f"long_window ({v}) must be greater than short_window ({short})")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "BacktestRequest":
        if self.start_date >= self.end_date:
            raise ValueError(
                f"end_date ({self.end_date}) must be after start_date ({self.start_date})."
            )
        return self


class BacktestResult(BaseModel):
    """Response model for a completed backtest run."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_name: str
    ticker: str
    short_window: int
    long_window: int
    start_date: str
    end_date: str
    total_return: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    num_trades: int | None
    created_at: datetime


class BacktestResultWithCurve(BacktestResult):
    """Extended response that also includes the full equity curve."""

    equity_curve: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {date: str, value: float} dicts for the equity curve chart",
    )


class StrategyResponse(BaseModel):
    """Response model for a strategy record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    default_ticker: str
    created_at: datetime
