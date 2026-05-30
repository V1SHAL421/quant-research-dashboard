"""
Integration tests for the FastAPI backend.

Uses httpx's AsyncClient with the ASGI transport so no actual server is
needed.  The SQLite database is replaced with an in-memory instance for
each test session to avoid polluting the real quant_research.db file.

yfinance.download is always mocked to keep tests fast and offline-safe.
"""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///./test_quant_research.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Any, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create the test database schema once per session, drop it after."""
    # We need the models to be imported before create_all
    from backend.models.backtest import BacktestRun, Strategy  # noqa: F401

    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db

    yield

    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()

    # Remove test DB file
    import os

    try:
        os.remove("./test_quant_research.db")
    except FileNotFoundError:
        pass


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_df(n: int = 400, seed: int = 0) -> pd.DataFrame:
    """Synthetic price DataFrame mimicking yfinance output."""
    rng = np.random.default_rng(seed)
    prices = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
    index = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"Close": prices}, index=index)


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ticker": "SPY",
        "short_window": 10,
        "long_window": 30,
        "start_date": "2020-01-01",
        "end_date": "2022-01-01",
        "strategy_name": "MA Crossover",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/strategies
# ---------------------------------------------------------------------------


class TestStrategiesEndpoint:
    def test_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_each_strategy_has_required_fields(self, client: TestClient) -> None:
        resp = client.get("/api/strategies")
        data = resp.json()
        required = {"id", "name", "description", "default_ticker", "created_at"}
        for strategy in data:
            assert required.issubset(strategy.keys()), f"Missing keys in {strategy}"

    def test_strategies_ordered_alphabetically(self, client: TestClient) -> None:
        resp = client.get("/api/strategies")
        data = resp.json()
        names = [s["name"] for s in data]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# GET /api/backtests
# ---------------------------------------------------------------------------


class TestListBacktests:
    def test_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/backtests")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_limit_query_param(self, client: TestClient) -> None:
        resp = client.get("/api/backtests?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 5


# ---------------------------------------------------------------------------
# POST /api/backtests/run
# ---------------------------------------------------------------------------


class TestRunBacktest:
    @patch("backend.services.backtest_engine.yf.download")
    def test_successful_run_returns_201(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        payload = _valid_payload()
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 201

    @patch("backend.services.backtest_engine.yf.download")
    def test_response_has_required_fields(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        payload = _valid_payload()
        resp = client.post("/api/backtests/run", json=payload)
        data = resp.json()
        required = {
            "id", "strategy_name", "ticker", "short_window", "long_window",
            "start_date", "end_date", "total_return", "sharpe_ratio",
            "max_drawdown", "num_trades", "created_at", "equity_curve",
        }
        assert required.issubset(data.keys())

    @patch("backend.services.backtest_engine.yf.download")
    def test_equity_curve_in_response(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        resp = client.post("/api/backtests/run", json=_valid_payload())
        data = resp.json()
        assert isinstance(data["equity_curve"], list)
        assert len(data["equity_curve"]) > 0
        first = data["equity_curve"][0]
        assert "date" in first and "value" in first

    @patch("backend.services.backtest_engine.yf.download")
    def test_run_persisted_in_db(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        before_resp = client.get("/api/backtests")
        count_before = len(before_resp.json())

        client.post("/api/backtests/run", json=_valid_payload())

        after_resp = client.get("/api/backtests")
        count_after = len(after_resp.json())
        assert count_after == count_before + 1

    @patch("backend.services.backtest_engine.yf.download")
    def test_ticker_normalised_to_uppercase(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        payload = _valid_payload(ticker="spy")
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "SPY"

    def test_validation_error_long_must_exceed_short(self, client: TestClient) -> None:
        payload = _valid_payload(short_window=50, long_window=20)
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 422

    def test_empty_ticker_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload(ticker="")
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 422

    @patch("backend.services.backtest_engine.yf.download")
    def test_empty_price_data_returns_422(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = pd.DataFrame()
        resp = client.post("/api/backtests/run", json=_valid_payload(ticker="INVALID"))
        assert resp.status_code == 422

    @patch("backend.services.backtest_engine.yf.download")
    def test_metrics_are_numbers(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        resp = client.post("/api/backtests/run", json=_valid_payload())
        data = resp.json()
        assert isinstance(data["total_return"], (int, float))
        # sharpe_ratio may be None when std is zero (degenerate input)
        assert data["sharpe_ratio"] is None or isinstance(data["sharpe_ratio"], (int, float))
        assert isinstance(data["max_drawdown"], (int, float))
        assert isinstance(data["num_trades"], int)

    def test_end_date_before_start_date_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload(start_date="2023-01-01", end_date="2022-01-01")
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 422

    def test_same_start_end_date_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload(start_date="2022-01-01", end_date="2022-01-01")
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 422

    def test_invalid_ticker_chars_returns_422(self, client: TestClient) -> None:
        payload = _valid_payload(ticker="SP Y")  # embedded space
        resp = client.post("/api/backtests/run", json=payload)
        assert resp.status_code == 422

    @patch("backend.services.backtest_engine.yf.download")
    def test_network_error_returns_503(self, mock_dl: MagicMock, client: TestClient) -> None:
        # Any exception from yf.download is normalised to ConnectionError → 503
        mock_dl.side_effect = Exception("network down")
        resp = client.post("/api/backtests/run", json=_valid_payload())
        assert resp.status_code == 503

    @patch("backend.services.backtest_engine.yf.download")
    def test_multiple_runs_incrementing_ids(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        resp1 = client.post("/api/backtests/run", json=_valid_payload())
        resp2 = client.post("/api/backtests/run", json=_valid_payload(ticker="QQQ"))
        assert resp1.json()["id"] < resp2.json()["id"]

    @patch("backend.services.backtest_engine.yf.download")
    def test_list_ordered_newest_first(self, mock_dl: MagicMock, client: TestClient) -> None:
        mock_dl.return_value = _make_price_df()
        client.post("/api/backtests/run", json=_valid_payload())
        client.post("/api/backtests/run", json=_valid_payload(ticker="IWM"))

        resp = client.get("/api/backtests")
        data = resp.json()
        if len(data) >= 2:
            # Newer runs should appear first (higher id)
            assert data[0]["id"] >= data[1]["id"]
