"""
Backtest callbacks.

All data fetching goes through HTTP calls to the FastAPI backend.
No database access, no business logic — pure UI orchestration.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import plotly.graph_objects as go
import requests
from dash import Input, Output, State, no_update

from dashboard.utils import base_figure_layout, empty_equity_figure

logger = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api")
REQUEST_TIMEOUT = 120  # seconds — backtests can take time to download data

_HISTORY_SENTINEL = "__fetch_failed__"


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------


def register_callbacks(app: Any) -> None:  # noqa: ANN401
    """Register all backtest-related Dash callbacks on *app*."""

    # ------------------------------------------------------------------
    # Slider label callbacks (instant feedback, no API call)
    # ------------------------------------------------------------------

    @app.callback(
        Output("short-window-display", "children"),
        Input("short-window-slider", "value"),
    )
    def update_short_label(value: int) -> int:
        return value

    @app.callback(
        Output("long-window-display", "children"),
        Input("long-window-slider", "value"),
    )
    def update_long_label(value: int) -> int:
        return value

    # ------------------------------------------------------------------
    # Main backtest callback
    # ------------------------------------------------------------------

    @app.callback(
        Output("metric-total-return", "children"),
        Output("metric-sharpe", "children"),
        Output("metric-max-drawdown", "children"),
        Output("metric-num-trades", "children"),
        Output("equity-curve-chart", "figure"),
        Output("history-table", "data"),
        Output("error-alert", "children"),
        Output("error-alert", "is_open"),
        Output("spinner-placeholder", "children"),
        Input("run-backtest-btn", "n_clicks"),
        State("ticker-input", "value"),
        State("short-window-slider", "value"),
        State("long-window-slider", "value"),
        State("start-date-picker", "date"),
        State("end-date-picker", "date"),
        State("strategy-dropdown", "value"),
        prevent_initial_call=True,
    )
    def run_backtest(
        n_clicks: int,
        ticker: str | None,
        short_window: int,
        long_window: int,
        start_date: str | None,
        end_date: str | None,
        strategy_name: str | None,
    ) -> tuple[Any, ...]:
        """
        Triggered when the user clicks "Run Backtest".

        1. POST /api/backtests/run  → get metrics + equity curve
        2. GET  /api/backtests      → refresh history table
        3. Return updated UI elements
        """
        empty_fig = empty_equity_figure()

        # ---- Input validation (client-side guard) ---------------------
        validation_error = _validate_inputs(ticker, short_window, long_window, start_date, end_date)
        if validation_error:
            return _error_return(validation_error, empty_fig)

        assert ticker is not None and start_date is not None and end_date is not None  # narrowing

        payload = {
            "ticker": ticker.strip().upper(),
            "short_window": short_window,
            "long_window": long_window,
            "start_date": _strip_date(start_date),
            "end_date": _strip_date(end_date),
            "strategy_name": strategy_name or "MA Crossover",
        }

        # ---- POST /api/backtests/run ----------------------------------
        response: requests.Response | None = None
        try:
            response = requests.post(
                f"{API_BASE}/backtests/run",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            return _error_return(
                f"Cannot connect to the backend API ({API_BASE}). Is it running?",
                empty_fig,
            )
        except requests.exceptions.Timeout:
            return _error_return(
                "The backtest request timed out. Try a shorter date range.",
                empty_fig,
            )
        except requests.exceptions.HTTPError as exc:
            detail = _extract_error_detail(response)
            logger.warning("Backtest API error %s: %s", exc.response.status_code, detail)
            return _error_return(f"Backtest error: {detail}", empty_fig)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error calling backtest API")
            return _error_return(f"Unexpected error: {exc}", empty_fig)

        result: dict[str, Any] = response.json()

        # ---- Build equity curve chart --------------------------------
        equity_curve: list[dict[str, Any]] = result.get("equity_curve", [])
        fig = _build_equity_curve(equity_curve, ticker.upper(), short_window, long_window)

        # ---- Format metric cards ------------------------------------
        total_return = result.get("total_return")
        sharpe_ratio = result.get("sharpe_ratio")
        max_drawdown = result.get("max_drawdown")
        num_trades = result.get("num_trades")

        total_return_str = f"{total_return * 100:+.2f} %" if total_return is not None else "N/A"
        sharpe_ratio_str = f"{sharpe_ratio:.3f}" if sharpe_ratio is not None else "N/A"
        max_drawdown_str = f"{max_drawdown * 100:.2f} %" if max_drawdown is not None else "N/A"
        num_trades_str = str(num_trades) if num_trades is not None else "N/A"

        # ---- GET /api/backtests for history table --------------------
        history_data = _fetch_history()
        history_output = no_update if history_data == _HISTORY_SENTINEL else history_data

        return (
            total_return_str,
            sharpe_ratio_str,
            max_drawdown_str,
            num_trades_str,
            fig,
            history_output,
            "",     # error message (empty)
            False,  # error alert hidden
            "",     # spinner placeholder
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_inputs(
    ticker: str | None,
    short_window: int,
    long_window: int,
    start_date: str | None,
    end_date: str | None,
) -> str | None:
    """Return an error message string if any input is invalid, else None."""
    if not ticker or not ticker.strip():
        return "Please enter a valid ticker symbol."
    if long_window <= short_window:
        return f"Long MA window ({long_window}) must be greater than Short MA window ({short_window})."
    if not start_date or not end_date:
        return "Please select both a start date and an end date."
    if _strip_date(start_date) >= _strip_date(end_date):
        return f"End date ({_strip_date(end_date)}) must be after start date ({_strip_date(start_date)})."
    return None


def _error_return(message: str, fig: go.Figure) -> tuple[Any, ...]:
    """Return the standard 9-tuple for an error state in the main callback."""
    return no_update, no_update, no_update, no_update, fig, no_update, message, True, ""


def _strip_date(date_str: str) -> str:
    """Strip the time component from a datetime string, returning only YYYY-MM-DD."""
    return date_str[:10]


def _fetch_history() -> list[dict[str, Any]] | str:
    """GET /api/backtests and return formatted rows for the DataTable.

    Returns the sentinel string ``_HISTORY_SENTINEL`` on any failure so the
    caller can emit ``no_update`` rather than clearing the table.
    """
    try:
        resp = requests.get(f"{API_BASE}/backtests", timeout=10)
        resp.raise_for_status()
        rows: list[dict[str, Any]] = resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to fetch backtest history", exc_info=True)
        return _HISTORY_SENTINEL

    return [_format_history_row(row) for row in rows]


def _format_history_row(row: dict[str, Any]) -> dict[str, Any]:
    """Format a raw backtest history row for display in the DataTable."""
    total_return = row.get("total_return")
    sharpe_ratio = row.get("sharpe_ratio")
    max_drawdown = row.get("max_drawdown")
    created_at = row.get("created_at", "")

    return {
        "id": row.get("id"),
        "strategy_name": row.get("strategy_name"),
        "ticker": row.get("ticker"),
        "short_window": row.get("short_window"),
        "long_window": row.get("long_window"),
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
        "total_return": f"{total_return * 100:+.2f}%" if total_return is not None else "N/A",
        "sharpe_ratio": f"{sharpe_ratio:.3f}" if sharpe_ratio is not None else "N/A",
        "max_drawdown": f"{max_drawdown * 100:.2f}%" if max_drawdown is not None else "N/A",
        "num_trades": row.get("num_trades"),
        "created_at": created_at[:19].replace("T", " ") if created_at else "",
    }


def _build_equity_curve(
    equity_curve: list[dict[str, Any]],
    ticker: str,
    short_window: int,
    long_window: int,
) -> go.Figure:
    """Build a Plotly Figure for the equity curve."""
    fig = go.Figure()

    if equity_curve:
        dates = [pt["date"] for pt in equity_curve]
        values = [pt["value"] for pt in equity_curve]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=values,
                mode="lines",
                name=f"{ticker} MA({short_window},{long_window})",
                line=dict(color="#00e676", width=2),
                fill="tozeroy",
                fillcolor="rgba(0, 230, 118, 0.08)",
                hovertemplate="Date: %{x}<br>Portfolio Value: %{y:.4f}<extra></extra>",
            )
        )

        fig.add_hline(
            y=1.0,
            line_dash="dash",
            line_color="#888",
            annotation_text="Break-even (1.0)",
            annotation_position="top left",
        )

    fig.update_layout(
        **base_figure_layout(),
        xaxis=dict(
            showgrid=True,
            gridcolor="#333",
            title="Date",
            tickformat="%Y-%m",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#333",
            title="Portfolio Value (normalised)",
            tickformat=".3f",
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0.4)"),
        margin=dict(l=60, r=20, t=20, b=50),
        hovermode="x unified",
    )

    return fig


def _extract_error_detail(response: requests.Response | None) -> str:
    """Attempt to extract a human-readable error message from a non-2xx response."""
    if response is None:
        return "No response received from server."
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("detail", "")
            if isinstance(detail, list):
                # Pydantic validation errors
                messages = [err.get("msg", str(err)) for err in detail]
                return "; ".join(messages)
            return str(detail) if detail else response.text
    except Exception:  # noqa: BLE001
        pass
    return response.text or f"HTTP {response.status_code}"
