"""
Unit tests for the backtest engine.

These tests use synthetic price data to avoid network calls, making them
fast and deterministic. yfinance.download is mocked at the module boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from backend.services.backtest_engine import (
    _annualised_sharpe,
    _compute_equity_curve,
    _compute_signals,
    _count_trades,
    _equity_curve_to_records,
    _max_drawdown,
    _total_return,
    run_ma_crossover,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_prices(n: int = 500, seed: int = 42, drift: float = 0.0003) -> pd.Series:
    """
    Generate synthetic daily price series with a positive drift via geometric
    Brownian motion.
    """
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(drift, 0.01, n)
    prices = 100 * np.exp(np.cumsum(log_returns))
    index = pd.date_range(start="2019-01-01", periods=n, freq="B")
    return pd.Series(prices, index=index, name="Close")


def _make_returns(prices: pd.Series) -> pd.Series:
    """Compute daily returns from a price series, matching the engine's convention."""
    return prices.pct_change().fillna(0.0)


def _call_run_ma_crossover(**overrides: Any) -> dict[str, Any]:
    """Call run_ma_crossover with sensible defaults, allowing per-test overrides."""
    defaults: dict[str, Any] = {
        "ticker": "TEST",
        "short_window": 10,
        "long_window": 30,
        "start_date": "2019-01-01",
        "end_date": "2021-01-01",
    }
    defaults.update(overrides)
    return run_ma_crossover(**defaults)


# ---------------------------------------------------------------------------
# _compute_signals
# ---------------------------------------------------------------------------


class TestComputeSignals:
    def test_returns_series_same_length(self) -> None:
        prices = _make_prices(200)
        signals = _compute_signals(prices, short_window=10, long_window=30)
        assert len(signals) == len(prices)

    def test_signals_only_plus_minus_one(self) -> None:
        prices = _make_prices(200)
        signals = _compute_signals(prices, short_window=10, long_window=30)
        assert set(signals.dropna().unique()).issubset({1, -1})

    def test_no_lookahead_leading_values_filled(self) -> None:
        """Before the long SMA warms up, signals should still be ±1 (fillna → -1)."""
        prices = _make_prices(50)
        signals = _compute_signals(prices, short_window=5, long_window=20)
        assert signals.isna().sum() == 0

    def test_trending_up_produces_long_signal(self) -> None:
        """Monotonically rising prices should produce predominantly +1 signals."""
        index = pd.date_range("2020-01-01", periods=200, freq="B")
        prices = pd.Series(np.linspace(100, 200, 200), index=index)
        signals = _compute_signals(prices, short_window=10, long_window=30)
        # After warm-up, the short SMA should be above the long SMA
        warmed_up = signals.iloc[30:]
        assert (warmed_up == 1).mean() > 0.8


# ---------------------------------------------------------------------------
# _compute_equity_curve
# ---------------------------------------------------------------------------


class TestComputeEquityCurve:
    def test_starts_near_one(self) -> None:
        prices = _make_prices(200)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 10, 30)
        equity = _compute_equity_curve(daily_returns, signals)
        assert abs(equity.dropna().iloc[0] - 1.0) < 0.05

    def test_always_positive(self) -> None:
        prices = _make_prices(300)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 10, 30)
        equity = _compute_equity_curve(daily_returns, signals)
        assert (equity > 0).all()

    def test_length_matches_prices(self) -> None:
        prices = _make_prices(200)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 10, 30)
        equity = _compute_equity_curve(daily_returns, signals)
        assert len(equity) == len(prices)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def _equity(self) -> pd.Series:
        prices = _make_prices(500)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 20, 50)
        return _compute_equity_curve(daily_returns, signals)

    def test_total_return_type(self) -> None:
        equity = self._equity()
        result = _total_return(equity)
        assert isinstance(result, float)

    def test_total_return_empty(self) -> None:
        assert _total_return(pd.Series([], dtype=float)) == 0.0

    def test_sharpe_finite_or_none(self) -> None:
        prices = _make_prices(500)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 20, 50)
        sharpe = _annualised_sharpe(daily_returns, signals)
        assert sharpe is None or np.isfinite(sharpe)

    def test_sharpe_positive_for_trending_market(self) -> None:
        """Strongly trending prices with correct signal should have positive Sharpe."""
        index = pd.date_range("2018-01-01", periods=600, freq="B")
        prices = pd.Series(np.linspace(100, 400, 600), index=index)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 20, 50)
        sharpe = _annualised_sharpe(daily_returns, signals)
        assert sharpe is not None and sharpe > 0

    def test_sharpe_returns_none_for_flat_prices(self) -> None:
        """All-identical prices → zero std → should return None, not 0.0."""
        index = pd.date_range("2020-01-01", periods=200, freq="B")
        prices = pd.Series([100.0] * 200, index=index)
        daily_returns = _make_returns(prices)
        signals = _compute_signals(prices, 10, 30)
        sharpe = _annualised_sharpe(daily_returns, signals)
        assert sharpe is None

    def test_max_drawdown_negative_or_zero(self) -> None:
        equity = self._equity()
        dd = _max_drawdown(equity)
        assert dd <= 0.0

    def test_max_drawdown_bounded(self) -> None:
        equity = self._equity()
        dd = _max_drawdown(equity)
        assert -1.0 <= dd <= 0.0

    def test_max_drawdown_empty(self) -> None:
        assert _max_drawdown(pd.Series([], dtype=float)) == 0.0

    def test_count_trades_nonnegative(self) -> None:
        prices = _make_prices(300)
        signals = _compute_signals(prices, 10, 30)
        trades = _count_trades(signals)
        assert trades >= 0

    def test_count_trades_flat_signal_is_zero(self) -> None:
        """A constant signal should produce no trades."""
        index = pd.date_range("2020-01-01", periods=100, freq="B")
        signals = pd.Series([1] * 100, index=index)
        assert _count_trades(signals) == 0


# ---------------------------------------------------------------------------
# _equity_curve_to_records
# ---------------------------------------------------------------------------


class TestEquityCurveToRecords:
    def _equity(self) -> pd.Series:
        prices = _make_prices(100)
        signals = _compute_signals(prices, 10, 30)
        return _compute_equity_curve(_make_returns(prices), signals)

    def test_output_structure(self) -> None:
        records = _equity_curve_to_records(self._equity())
        assert isinstance(records, list)
        assert len(records) > 0
        first = records[0]
        assert "date" in first
        assert "value" in first

    def test_dates_are_strings(self) -> None:
        for record in _equity_curve_to_records(self._equity()):
            assert isinstance(record["date"], str)
            assert isinstance(record["value"], float)

    def test_values_rounded_to_6dp(self) -> None:
        for record in _equity_curve_to_records(self._equity()):
            str_val = str(record["value"])
            if "." in str_val:
                assert len(str_val.split(".")[1]) <= 6


# ---------------------------------------------------------------------------
# run_ma_crossover (integration — mocked yfinance)
# ---------------------------------------------------------------------------


class TestRunMaCrossover:
    @patch("backend.services.backtest_engine.yf.download")
    def test_returns_all_required_keys(self, mock_dl: MagicMock) -> None:
        prices = _make_prices(500)
        mock_dl.return_value = pd.DataFrame({"Close": prices})
        result = _call_run_ma_crossover()
        assert {"total_return", "sharpe_ratio", "max_drawdown", "num_trades", "equity_curve"} == set(result.keys())

    @patch("backend.services.backtest_engine.yf.download")
    def test_equity_curve_is_list_of_dicts(self, mock_dl: MagicMock) -> None:
        prices = _make_prices(500)
        mock_dl.return_value = pd.DataFrame({"Close": prices})
        result = _call_run_ma_crossover()
        assert isinstance(result["equity_curve"], list)
        assert len(result["equity_curve"]) > 0
        assert "date" in result["equity_curve"][0]
        assert "value" in result["equity_curve"][0]

    @patch("backend.services.backtest_engine.yf.download")
    def test_raises_value_error_for_empty_data(self, mock_dl: MagicMock) -> None:
        mock_dl.return_value = pd.DataFrame()
        with pytest.raises(ValueError, match="No price data"):
            _call_run_ma_crossover()

    @patch("backend.services.backtest_engine.yf.download")
    def test_metrics_are_finite(self, mock_dl: MagicMock) -> None:
        prices = _make_prices(500)
        mock_dl.return_value = pd.DataFrame({"Close": prices})
        result = _call_run_ma_crossover()
        assert np.isfinite(result["total_return"])
        assert result["sharpe_ratio"] is None or np.isfinite(result["sharpe_ratio"])
        assert np.isfinite(result["max_drawdown"])
        assert isinstance(result["num_trades"], int)

    @patch("backend.services.backtest_engine.yf.download")
    def test_equity_curve_downsampled(self, mock_dl: MagicMock) -> None:
        """Equity curve should not exceed 1000 points."""
        prices = _make_prices(3000)
        mock_dl.return_value = pd.DataFrame({"Close": prices})
        result = _call_run_ma_crossover()
        assert len(result["equity_curve"]) <= 1000

    @patch("backend.services.backtest_engine.yf.download")
    def test_multiindex_column_handled(self, mock_dl: MagicMock) -> None:
        """MultiIndex column output from yfinance is handled gracefully."""
        prices = _make_prices(300)
        multi_df = pd.DataFrame({"Close": prices})
        multi_df.columns = pd.MultiIndex.from_tuples([("Close", "TEST")])
        mock_dl.return_value = multi_df
        result = _call_run_ma_crossover()
        assert "total_return" in result

    @patch("backend.services.backtest_engine.yf.download")
    def test_network_error_raises_connection_error(self, mock_dl: MagicMock) -> None:
        """Any exception from yf.download is normalised to ConnectionError."""
        mock_dl.side_effect = Exception("network down")
        with pytest.raises(ConnectionError, match="Network error"):
            _call_run_ma_crossover()
