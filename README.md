# Quantitative Research Dashboard

A portfolio project demonstrating production-quality quant engineering skills. Features a FastAPI backend with SQLAlchemy ORM, a Dash frontend with Bootstrap styling, and a Moving Average Crossover backtest engine built on pandas + yfinance.

Built as a portfolio project for quant internship applications (Qube Research & Technologies).

---

## Architecture

```
FastAPI (port 8000)          Dash (port 8050)
─────────────────────        ──────────────────────────
backend/
  main.py          ◄───────  dashboard/callbacks/backtest.py
  routes/
    backtests.py             (HTTP POST /api/backtests/run)
    strategies.py            (HTTP GET  /api/strategies)
  services/
    backtest_engine.py       (pure functions, no I/O side-effects)
  models/
    backtest.py              (SQLAlchemy ORM)
  schemas/
    backtest.py              (Pydantic v2)
  database.py                (SQLite engine + session factory)
```

Key design decisions:
- **No business logic in callbacks** — callbacks only make HTTP calls to the backend.
- **Pure engine functions** — `backtest_engine.py` is fully testable without a database or server.
- **Pydantic v2 schemas** — typed request/response contracts with field-level validation.
- **No circular imports** — models do not import routes or services.

---

## Backtest Engine

The MA Crossover strategy:

1. Downloads adjusted closing prices via `yfinance`.
2. Computes short-period SMA and long-period SMA.
3. **Signal** (no look-ahead): position = +1 if short SMA > long SMA (yesterday's values), else −1.
4. **Strategy return** = signal × daily return.
5. **Equity curve** = cumulative product of (1 + strategy return).
6. Reports: total return, annualised Sharpe (252 days, rf=0), max drawdown, # of signal flips.

---

## Quick Start

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch both services
python run.py
```

- Dashboard: http://localhost:8050
- API docs (Swagger): http://localhost:8000/docs
- API docs (ReDoc): http://localhost:8000/redoc

### Run backend or frontend independently

```bash
# Backend only
python run.py --backend-only

# Frontend only (assumes backend is running)
python run.py --frontend-only

# Disable uvicorn auto-reload (production-like)
python run.py --no-reload
```

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite:
- Uses an in-memory SQLite database — no side-effects on `quant_research.db`.
- Mocks `yfinance.download` for fast, offline-safe tests.
- Covers engine unit tests (signals, metrics, equity curve) and API integration tests.

---

## API Reference

### `GET /api/strategies`
Returns all registered strategies.

### `GET /api/backtests?limit=50`
Returns the most recent backtest runs (newest first).

### `POST /api/backtests/run`
Runs a backtest and persists the result.

**Request body:**
```json
{
  "ticker": "SPY",
  "short_window": 20,
  "long_window": 50,
  "start_date": "2020-01-01",
  "end_date": "2024-01-01",
  "strategy_name": "MA Crossover"
}
```

**Response:** BacktestResult + `equity_curve` list of `{date, value}` points.

---

## Project Structure

```
Dash/
├── backend/
│   ├── main.py              # FastAPI app, CORS, router includes
│   ├── database.py          # SQLAlchemy engine + session + init_db
│   ├── models/backtest.py   # Strategy + BacktestRun ORM models
│   ├── schemas/backtest.py  # Pydantic request/response schemas
│   ├── routes/
│   │   ├── backtests.py     # GET /backtests, POST /backtests/run
│   │   └── strategies.py   # GET /strategies
│   └── services/
│       └── backtest_engine.py  # Pure MA crossover backtest logic
├── dashboard/
│   ├── app.py               # Dash app + layout + callback registration
│   ├── callbacks/backtest.py   # UI callbacks (HTTP only, no DB)
│   └── components/
│       ├── controls.py      # Input sidebar (ticker, MA sliders, dates)
│       └── results.py       # KPI cards + equity curve + history table
├── tests/
│   ├── test_backtest_engine.py  # Engine unit tests (mocked yfinance)
│   └── test_api.py              # FastAPI integration tests
├── run.py                   # Concurrent launcher (backend + frontend)
└── requirements.txt
```

---

## Linting

```bash
ruff check .
ruff format .
```
