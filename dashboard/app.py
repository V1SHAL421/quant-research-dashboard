"""
Dash application entry point.

Start with:
    python run.py             (starts both backend and frontend)
    python -m dashboard.app   (frontend only, assumes backend is running)
"""

from __future__ import annotations

import logging

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

from dashboard.callbacks.backtest import register_callbacks
from dashboard.components.controls import create_controls
from dashboard.components.results import create_results_panel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dash application
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        dbc.icons.BOOTSTRAP,
    ],
    suppress_callback_exceptions=True,
    title="Quant Research Dashboard",
    update_title="Running…",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
    ],
)

server = app.server  # expose Flask server for production WSGI deployment


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _navbar() -> dbc.Navbar:
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            html.I(className="bi bi-activity text-success fs-3 me-2"),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.NavbarBrand(
                                "Quantitative Research Dashboard",
                                className="fw-bold fs-5 text-white mb-0",
                            ),
                            width="auto",
                        ),
                    ],
                    align="center",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            html.Small(
                                "MA Crossover Backtesting Engine  ·  Qube Research & Technologies",
                                className="text-muted",
                            ),
                            width="auto",
                        ),
                    ],
                    align="center",
                    className="ms-auto",
                ),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        className="mb-0 border-bottom border-secondary",
        style={"borderBottom": "2px solid #198754 !important"},
    )


app.layout = dbc.Container(
    [
        # ---- Navbar -------------------------------------------------------
        dbc.Row(dbc.Col(_navbar()), className="mb-3"),

        # ---- Subtitle / intro strip --------------------------------------
        dbc.Row(
            dbc.Col(
                dbc.Alert(
                    [
                        html.Strong("How it works: "),
                        "Configure your parameters on the left, then click ",
                        html.Strong("Run Backtest"),
                        ". The engine downloads price data via yfinance, computes "
                        "SMA signals, and reports annualised Sharpe, total return, "
                        "max drawdown and number of trades.",
                    ],
                    color="secondary",
                    className="py-2 mb-3",
                )
            )
        ),

        # ---- Main content: sidebar + results -----------------------------
        dbc.Row(
            [
                # Left sidebar — controls
                dbc.Col(
                    create_controls(),
                    xs=12,
                    md=3,
                    className="mb-4 mb-md-0",
                ),

                # Right main area — results
                dbc.Col(
                    [
                        dcc.Loading(
                            id="global-loading",
                            type="circle",
                            color="#198754",
                            children=create_results_panel(),
                        ),
                    ],
                    xs=12,
                    md=9,
                ),
            ],
            className="g-4",
        ),

        # ---- Footer -------------------------------------------------------
        dbc.Row(
            dbc.Col(
                html.Hr(className="border-secondary mt-5"),
            )
        ),
        dbc.Row(
            dbc.Col(
                html.Small(
                    [
                        "Built with ",
                        html.A("FastAPI", href="https://fastapi.tiangolo.com", target="_blank"),
                        " + ",
                        html.A("Dash", href="https://dash.plotly.com", target="_blank"),
                        " + ",
                        html.A("yfinance", href="https://github.com/ranaroussi/yfinance", target="_blank"),
                        ".  For educational purposes only — not financial advice.",
                    ],
                    className="text-muted",
                ),
                className="text-center mb-4",
            )
        ),
    ],
    fluid=True,
    className="px-4",
)

# ---------------------------------------------------------------------------
# Register callbacks
# ---------------------------------------------------------------------------

register_callbacks(app)


# ---------------------------------------------------------------------------
# Development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
