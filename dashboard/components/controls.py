"""
Left-sidebar controls card.

Contains all user inputs: ticker, MA windows, date range, and run button.
No callback logic lives here — this module only builds the layout.
"""

from __future__ import annotations

from datetime import date

import dash_bootstrap_components as dbc
from dash import dcc, html


def create_controls() -> dbc.Card:
    """Return the full controls card for the left sidebar."""
    return dbc.Card(
        [
            dbc.CardHeader(
                html.H5("Backtest Parameters", className="mb-0 text-white"),
                className="bg-primary",
            ),
            dbc.CardBody(
                [
                    # ---- Ticker ----------------------------------------
                    dbc.Label("Ticker Symbol", html_for="ticker-input", className="fw-bold"),
                    dbc.Input(
                        id="ticker-input",
                        type="text",
                        value="SPY",
                        placeholder="e.g. SPY, QQQ, AAPL",
                        maxLength=10,
                        className="mb-3",
                        debounce=True,
                    ),

                    # ---- Short MA window --------------------------------
                    dbc.Label(
                        [
                            "Short MA Window: ",
                            html.Span(id="short-window-display", className="text-info fw-bold"),
                            " days",
                        ],
                        className="fw-bold",
                    ),
                    dcc.Slider(
                        id="short-window-slider",
                        min=5,
                        max=50,
                        step=1,
                        value=20,
                        marks={5: "5", 10: "10", 20: "20", 30: "30", 40: "40", 50: "50"},
                        tooltip={"placement": "bottom", "always_visible": False},
                        className="mb-4",
                    ),

                    # ---- Long MA window ---------------------------------
                    dbc.Label(
                        [
                            "Long MA Window: ",
                            html.Span(id="long-window-display", className="text-info fw-bold"),
                            " days",
                        ],
                        className="fw-bold",
                    ),
                    dcc.Slider(
                        id="long-window-slider",
                        min=10,
                        max=200,
                        step=5,
                        value=50,
                        marks={10: "10", 50: "50", 100: "100", 150: "150", 200: "200"},
                        tooltip={"placement": "bottom", "always_visible": False},
                        className="mb-4",
                    ),

                    # ---- Date range -------------------------------------
                    dbc.Label("Start Date", html_for="start-date-picker", className="fw-bold"),
                    dcc.DatePickerSingle(
                        id="start-date-picker",
                        date="2020-01-01",
                        display_format="YYYY-MM-DD",
                        min_date_allowed=date(2000, 1, 1),
                        max_date_allowed=date.today(),
                        className="mb-3 d-block",
                        style={"width": "100%"},
                    ),

                    dbc.Label("End Date", html_for="end-date-picker", className="fw-bold"),
                    dcc.DatePickerSingle(
                        id="end-date-picker",
                        date="2024-01-01",
                        display_format="YYYY-MM-DD",
                        min_date_allowed=date(2000, 1, 2),
                        max_date_allowed=date.today(),
                        className="mb-4 d-block",
                        style={"width": "100%"},
                    ),

                    # ---- Strategy selector ------------------------------
                    dbc.Label("Strategy", html_for="strategy-dropdown", className="fw-bold"),
                    dcc.Dropdown(
                        id="strategy-dropdown",
                        options=[
                            {"label": "MA Crossover", "value": "MA Crossover"},
                            {"label": "Momentum", "value": "Momentum"},
                            {"label": "Mean Reversion", "value": "Mean Reversion"},
                        ],
                        value="MA Crossover",
                        clearable=False,
                        className="mb-4",
                    ),

                    # ---- Run button ------------------------------------
                    dbc.Button(
                        [
                            html.I(className="bi bi-play-fill me-2"),
                            "Run Backtest",
                        ],
                        id="run-backtest-btn",
                        color="success",
                        size="lg",
                        className="w-100",
                        n_clicks=0,
                    ),

                    # ---- Error alert -----------------------------------
                    dbc.Alert(
                        id="error-alert",
                        color="danger",
                        is_open=False,
                        dismissable=True,
                        className="mt-3 mb-0",
                    ),
                ]
            ),
        ],
        className="h-100 shadow-sm",
    )
