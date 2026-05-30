"""
Pure-function backtest engine.

No database access, no FastAPI dependencies — only pandas + yfinance.
All functions are straightforward to unit-test in isolation.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

# Decimal places used when rounding metric floats in the returned dict.
_METRIC_PRECISION = 6

# Minimum number of daily rows required to compute any meaningful MA signal.
_MIN_PRICE_ROWS = 10


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_ma_crossover(
    ticker: str,
    short_window: int,
    long_window: int,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """
    Run a Moving Average Crossover backtest.

    Parameters
    ----------
    ticker:
        Equity ticker symbol (e.g. "SPY").
    short_window:
        Short SMA lookback in trading days.
    long_window:
        Long SMA lookback in trading days.
    start_date:
        Backtest start date as "YYYY-MM-DD".
    end_date:
        Backtest end date as "YYYY-MM-DD".

    Returns
    -------
    dict with keys:
        total_return   – cumulative strategy return (e.g. 0.25 = +25 %)
        sharpe_ratio   – annualised Sharpe ratio (rf = 0, 252 trading days),
                         or None when it cannot be computed
        max_drawdown   – maximum peak-to-trough drawdown (e.g. -0.15 = -15 %)
        num_trades     – number of position changes (signal flips)
        equity_curve   – list of {"date": "YYYY-MM-DD", "value": float} dicts
                         representing the normalised portfolio value (starts at 1.0)

    Raises
    ------
    ConnectionError
        If the network request to yfinance fails.
    ValueError
        If the downloaded data is empty or too short to compute any signal.
    """
    prices = _download_prices(ticker, start_date, end_date)
    daily_returns = prices.pct_change().fillna(0.0)
    signals = _compute_signals(prices, short_window, long_window)
    equity_curve = _compute_equity_curve(daily_returns, signals)

    total_return = _total_return(equity_curve)
    sharpe_ratio = _annualised_sharpe(daily_returns, signals)
    max_drawdown = _max_drawdown(equity_curve)
    num_trades = _count_trades(signals)

    equity_records = _equity_curve_to_records(equity_curve, max_points=1000)

    return {
        "total_return": round(total_return, _METRIC_PRECISION),
        "sharpe_ratio": round(sharpe_ratio, _METRIC_PRECISION) if sharpe_ratio is not None else None,
        "max_drawdown": round(max_drawdown, _METRIC_PRECISION),
        "num_trades": num_trades,
        "equity_curve": equity_records,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _download_prices(ticker: str, start_date: str, end_date: str) -> pd.Series:
    """
    Download adjusted closing prices for *ticker* between start_date and end_date.

    Raises
    ------
    ConnectionError
        If any network-level failure occurs (DNS, timeout, rate-limit, etc.).
    ValueError
        If the download returns no data or fewer than _MIN_PRICE_ROWS rows.
    """
    try:
        raw = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        # yfinance can raise requests.RequestException or internal errors
        # (YFTzMissingError, YFRateLimitError, etc.). Normalise all of them
        # to ConnectionError so callers have a single network-failure contract.
        raise ConnectionError(
            f"Network error downloading data for '{ticker}': {exc}. "
            "Check your internet connection and try again."
        ) from exc

    if raw.empty:
        raise ValueError(
            f"No price data returned for ticker '{ticker}' "
            f"between {start_date} and {end_date}. "
            "Check that the ticker is valid and the date range is correct."
        )

    close = _extract_close_prices(raw)
    close = close.dropna()

    if len(close) < _MIN_PRICE_ROWS:
        raise ValueError(
            f"Insufficient price data for '{ticker}': only {len(close)} rows returned. "
            f"Need at least {_MIN_PRICE_ROWS}."
        )

    return close


def _extract_close_prices(raw: pd.DataFrame) -> pd.Series:
    """Extract the 'Close' column from a yfinance DataFrame.

    yfinance occasionally returns a MultiIndex column frame when called with
    a single ticker. This function handles both cases transparently.
    """
    if isinstance(raw.columns, pd.MultiIndex):
        return raw["Close"].iloc[:, 0]
    return raw["Close"]


def _compute_signals(
    prices: pd.Series, short_window: int, long_window: int
) -> pd.Series:
    """
    Compute position signals: +1 (long) when short SMA > long SMA, else -1 (short/flat).

    The signal on any given day is determined by *yesterday's* SMAs so there is no
    look-ahead bias — we trade at the open after the signal fires at the close.

    Returns a pd.Series of {+1, -1} aligned with *prices*.
    """
    short_sma = prices.rolling(window=short_window, min_periods=short_window).mean()
    long_sma = prices.rolling(window=long_window, min_periods=long_window).mean()

    # Shift by 1 to avoid look-ahead bias.
    raw_signal = (short_sma > long_sma).astype(int)
    signal = raw_signal.shift(1).fillna(0)
    # Map 0 → -1 (short/flat), 1 → +1 (long).
    return signal.map({1: 1, 0: -1})


def _compute_equity_curve(daily_returns: pd.Series, signals: pd.Series) -> pd.Series:
    """
    Compute the normalised equity curve (starts at 1.0).

    Daily P&L = signal(t) × daily_return(t)
    """
    strategy_returns = signals * daily_returns
    return (1 + strategy_returns).cumprod()


def _total_return(equity_curve: pd.Series) -> float:
    """Total return = final value / initial value − 1."""
    if equity_curve.empty:
        return 0.0
    return float(equity_curve.iloc[-1] - 1.0)


def _annualised_sharpe(
    daily_returns: pd.Series, signals: pd.Series, periods_per_year: int = 252
) -> float | None:
    """
    Annualised Sharpe ratio assuming risk-free rate = 0.

    Sharpe = mean(strategy_return) / std(strategy_return) × sqrt(252)

    Returns None when the ratio cannot be computed (no active trading period
    or zero variance). Callers should render None as "N/A", not 0.
    """
    strategy_returns = signals * daily_returns

    # Exclude the warm-up period before the long SMA first fires.
    first_active_index = signals.first_valid_index()
    if first_active_index is None:
        return None
    strategy_returns = strategy_returns.loc[first_active_index:]

    if strategy_returns.empty:
        return None

    std = strategy_returns.std()
    if std == 0 or np.isnan(std):
        return None

    sharpe = (strategy_returns.mean() / std) * np.sqrt(periods_per_year)
    result = float(sharpe)
    return result if np.isfinite(result) else None


def _max_drawdown(equity_curve: pd.Series) -> float:
    """
    Maximum peak-to-trough drawdown.

    Returns a negative float, e.g. -0.25 means a 25 % drawdown.
    """
    if equity_curve.empty:
        return 0.0

    rolling_max = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_max) / rolling_max
    return float(drawdowns.min())


def _count_trades(signals: pd.Series) -> int:
    """Count the number of position changes (signal flips)."""
    changes = signals.diff().abs()
    # Each flip from +1 to -1 (or vice versa) produces a diff of 2.
    return int((changes > 0).sum())


def _equity_curve_to_records(
    equity_curve: pd.Series, max_points: int = 1000
) -> list[dict[str, Any]]:
    """Convert equity curve Series to a JSON-serialisable list of dicts.

    Downsamples to at most *max_points* evenly-spaced rows to keep the HTTP
    response and chart render fast for long date ranges. The final point is
    always preserved so the reported total return matches the chart endpoint.
    """
    curve = equity_curve.dropna()
    if len(curve) > max_points:
        step = math.ceil(len(curve) / max_points)
        indices = list(range(0, len(curve), step))
        last = len(curve) - 1
        if indices[-1] != last:
            indices[-1] = last
        curve = curve.iloc[indices]

    records: list[dict[str, Any]] = []
    for timestamp, value in curve.items():
        if pd.isna(value):
            continue
        date_str = (
            timestamp.strftime("%Y-%m-%d")
            if hasattr(timestamp, "strftime")
            else str(timestamp)
        )
        records.append({"date": date_str, "value": round(float(value), _METRIC_PRECISION)})
    return records
